import socket
import struct
import crcmod
import sys
import os
import threading
import time

def zaciatok_funkcie(funkcia, zac):
    """
    Pomocna debuggovacia funkcia ktora vypise ktora funkcia bola prave spustena a ukoncena.

    :param funkcia: nazov funkcie
    :param zac: boolean ci zacina alebo konci
    :return:
    """

    if zac:
        text = "# Zaciatok funkcie {} #".format(funkcia)
    else:
        text = "# Koniec funkcie {} #".format(funkcia)

    ram = "#" * (len(text))

    print(ram)
    print(text)
    print(ram)


IP_HEADER_LENGTH = 20
UDP_HEADER_LENGTH = 8
ETH_II_PAYLOAD = 1500
MAX_SIZE_ON_WIRE = ETH_II_PAYLOAD - IP_HEADER_LENGTH - UDP_HEADER_LENGTH

FORMAT_HLAVICKY_DAT = "IIhc"
VELKOST_HLAVICKY_DAT = struct.calcsize(FORMAT_HLAVICKY_DAT)
MAX_DATA_SIZE = MAX_SIZE_ON_WIRE - VELKOST_HLAVICKY_DAT
MIN_DATA_SIZE = 1

KEEPALIVE_INTERVAL = 30

crc32_func = crcmod.mkCrcFun(0x104c11db7, initCrc=0, xorOut=0xFFFFFFFF)


def nacitaj_cislo(dolna_hranica, horna_hranica):

    while True:
        try:
            cislo = int(input("Zadaj cislo z intervalu <{} az {}>: ".format(dolna_hranica, horna_hranica)))
            if dolna_hranica <= cislo <= horna_hranica:
                return cislo
            else:
                print("Zadane cislo nie je z intervalu <{} az {}>".format(dolna_hranica, horna_hranica))
        except:
            print("Nebolo zadane cislo")


def vytvor_datovy_paket(poradove_cislo, velkost_dat, data, flag, chyba=False):
    crc = 0
    hlavicka = struct.pack(FORMAT_HLAVICKY_DAT, poradove_cislo, crc, velkost_dat + VELKOST_HLAVICKY_DAT, flag)
    crc = crc32_func(hlavicka + data)
    if chyba:
        crc -= 1
    hlavicka = struct.pack(FORMAT_HLAVICKY_DAT, poradove_cislo, crc, velkost_dat + VELKOST_HLAVICKY_DAT, flag)
    vysledok = hlavicka + data

    return vysledok
    # print(VELKOST_HLAVICKY_DAT)
    # print(type(vysledok))
    # print(len(vysledok))
    # print(" ".join("{:02x}".format(x) for x in vysledok))


def rozbal_datovy_paket(paket):
    poradove_cislo, crc, celkova_velkost, flag = struct.unpack(FORMAT_HLAVICKY_DAT, paket[:VELKOST_HLAVICKY_DAT])
    data = paket[VELKOST_HLAVICKY_DAT:]
    hlavicka = struct.pack(FORMAT_HLAVICKY_DAT, poradove_cislo, 0, celkova_velkost, flag)
    kontrolne_crc = crc32_func(hlavicka + data)
    if kontrolne_crc == crc:
        chyba = False
    else:
        chyba = True
    velkost_dat = celkova_velkost - VELKOST_HLAVICKY_DAT
    return poradove_cislo, velkost_dat, flag, data, chyba


def server_riadic():
    # port = int(input("SERVER - Zadaj port: "))
    port = 1234
    print("SERVER - Zvoleny port", port)
    server_ip_port = ("", port)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_ip_port)

    data, addr = server_socket.recvfrom(1500)
    rozbalene = rozbal_datovy_paket(data)
    otvorenie = False
    if rozbalene[2] == b"a":
        print("SERVER - Prijatie otvorenia spojenia z adresy {}".format(addr))
        inicializacny_paket = vytvor_datovy_paket(0, 0, b"", b"a")
        server_socket.sendto(inicializacny_paket, addr)
        otvorenie = True
    else:
        print("SERVER - Odmietnutie otvorenia spojenia z adresy {}".format(addr))
        inicializacny_paket = vytvor_datovy_paket(0, 0, b"", b"g")
        server_socket.sendto(inicializacny_paket, addr)

    if otvorenie:
        print("SERVER - Spojenie s {} bolo uspesne nadviazane".format(addr))
    else:
        print("SERVER - Zatvaram spojenie")
        server_socket.close()
        return

    # data2, addr2 = server_socket.recvfrom(1500)
    # if data2 == b"POTVRDENIE SPOJENIA K->S" and addr1 == addr2 and otvorenie:
    #     print("SERVER - Prijatie potvrdenia spojenia z adresy {}".format(addr1))
    #     print("SERVER - Spojenie s {} bolo uspesne nadviazane".format(addr1))
    # else:
    #     print("SERVER - Prijatie zamietnutia spojenia z adresy {}".format(addr1))
    #     print("SERVER - Zatvaram spojenie")
    #     server_socket.close()

    server_prijimac(server_socket, addr)
    server_socket.close()


def server_prijimac(server_socket, addr):

    slovnik_fragmentov = {}
    pole_poskodenych = []
    celkovy_pocet_fragmentov = -2

    datove_flagy = b"bcdef"
    textova_sprava = True

    server_socket.settimeout(3 * KEEPALIVE_INTERVAL)
    try:
        while True:
            paket, addr = server_socket.recvfrom(1500)
            poradove_cislo, velkost_dat, flag, data, chyba = rozbal_datovy_paket(paket)
            print("SERVER - prijal spravu cislo: {}, "
                  "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))
            if chyba:
                pole_poskodenych.append(poradove_cislo)
            elif flag in datove_flagy:
                slovnik_fragmentov[poradove_cislo] = data

            if flag == b"d" or flag == b"e" or flag == b"f":
                textova_sprava = False

            if flag == b"c" or flag == b"f":
                celkovy_pocet_fragmentov = poradove_cislo

            if flag == b"k":
                print("SERVER - prijatie keepalive")

            if textova_sprava:
                if len(slovnik_fragmentov) == celkovy_pocet_fragmentov:
                    sprava = b""
                    for i in range(1, celkovy_pocet_fragmentov + 1):
                        sprava += slovnik_fragmentov[i]
                    print("SERVER - cele znenie spravy:")
                    print(sprava.decode("utf-8"))
                    slovnik_fragmentov.clear()
                    celkovy_pocet_fragmentov = -2
            elif len(slovnik_fragmentov) == celkovy_pocet_fragmentov + 1:
                spojene = b""
                nazov_suboru = slovnik_fragmentov[0].decode("utf-8")
                priecinok = input("Zadaj cestu k priecinku, kde ma byt subor ulozeny: ")
                cesta = os.path.join(priecinok, nazov_suboru)
                subor = open(cesta, "wb")
                for i in range(1, celkovy_pocet_fragmentov + 1):
                    subor.write(slovnik_fragmentov[i])
                subor.close()
                print("Cesta k suboru je:", cesta)
                slovnik_fragmentov.clear()
                celkovy_pocet_fragmentov = -2
                textova_sprava = True

    except socket.timeout:
        print("SERVER - ukoncenie spojenia z dovodu neaktivity klienta")


ukonci = False


def posli_keepalive(klient_socket, server_ip_port, cas):
    print("KLIENT - posielanie keepalive spustene")
    while True:
        global ukonci
        if ukonci:
            return

        paket = vytvor_datovy_paket(0, 0, b"", b"k")
        klient_socket.sendto(paket, server_ip_port)
        print("KLIENT - poslal som keepalive")
        time.sleep(cas)


def spusti_keepalive(klient_socket, server_ip_port, cas):
    ukonci_keepalive()

    thread = threading.Thread(target=posli_keepalive, args=(klient_socket, server_ip_port, cas))
    thread.daemon = True
    global ukonci
    ukonci = False
    thread.start()


def ukonci_keepalive():
    global ukonci
    if not ukonci:
        print("KLIENT - posielanie keepalive zastavene")
    ukonci = True


def klient_riadic():
    # ip_adresa_servera = input("KLIENT - Zadaj IP adresu servera: ")
    # port = int(input("KLIENT - Zadaj port: "))
    ip_adresa_servera = "127.0.0.1"
    port = 1234
    print("KLIENT - Zvolena IP adresa servera", ip_adresa_servera)
    print("KLIENT - Zvoleny port", port)

    server_ip_port = (ip_adresa_servera, port)

    klient_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    inicializacny_paket = vytvor_datovy_paket(0, 0, b"", b"a")
    klient_socket.sendto(inicializacny_paket, server_ip_port)

    data, addr = klient_socket.recvfrom(1500)
    rozbalene = rozbal_datovy_paket(data)
    if addr == server_ip_port and rozbalene[2] == b"a":
        print("KLIENT - Spojenie so serverom {} bolo uspesne nadviazane".format(addr))
    else:
        print("KLIENT - Spojenie so serverom {} bolo zamietnute serverom".format(addr))
        print("KLIENT - Zatvaram spojenie")
        klient_socket.close()
        return

    volba = "Zadaj t pre odoslanie textovej spravy, zadaj s pre odoslanie suboru, zadaj x pre odhlasenie, " \
            "zadaj on pre spustenie keepalive, zadaj off pre ukoncenie posielania sprav keepalive: "
    rezim = input(volba)
    while rezim != "x":
        if rezim == "t":
            print("Zadaj velkost datoveho fragmentu")
            fragment_velkost = nacitaj_cislo(MIN_DATA_SIZE, MAX_DATA_SIZE)
            klient_vysielac_text(klient_socket, server_ip_port, fragment_velkost)
        elif rezim == "s":
            print("Zadaj velkost datoveho fragmentu")
            fragment_velkost = nacitaj_cislo(MIN_DATA_SIZE, MAX_DATA_SIZE)
            klient_vysielac_subor(klient_socket, server_ip_port, fragment_velkost)
        elif rezim == "on":
            spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
        elif rezim == "off":
            ukonci_keepalive()
        else:
            print("Nespravna volba")

        rezim = input(volba)

    klient_socket.close()


def fragmentuj(data, velkost_fragment):
    dolna_hranica = 0
    horna_hranica = 0
    dlzka_dat = len(data)
    pole_fragmentov = []
    while horna_hranica < dlzka_dat:
        horna_hranica += velkost_fragment
        pole_fragmentov.append(data[dolna_hranica:horna_hranica])
        dolna_hranica += velkost_fragment
    return pole_fragmentov


def klient_vysielac_text(klient_socket, server_ip_port, fragment_velkost):

    sprava = input("Zadaj spravu na odoslanie: ")
    # sprava = "q" * 10000
    data = sprava.encode()
    pole_fragmentov = fragmentuj(data, fragment_velkost)

    # data, addr = klient_socket.recvfrom(1500)

    ukonci_keepalive()

    poradove_cislo = 1
    for fragment in pole_fragmentov[:-1]:
        velkost_dat = len(fragment)
        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, b"b")
        klient_socket.sendto(paket, server_ip_port)
        poradove_cislo += 1
    fragment = pole_fragmentov[-1]
    velkost_dat = len(fragment)
    paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, b"c")
    klient_socket.sendto(paket, server_ip_port)

    spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
    return

    # while sprava != "":
    #     poradove_cislo = 0
    #     data = sprava.encode()
    #     velkost_dat = len(data)
    #     paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, data)
    #
    #     klient_socket.sendto(paket, server_ip_port)
    #
    #     sprava = input("Zadaj spravu na odoslanie: ")

    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("a" * 0).encode()), server_ip_port)
    # # OK 0
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("a" * 1).encode()), server_ip_port)
    # # OK 1
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("a" * 10).encode()), server_ip_port)
    # # OK 21
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("b" * 100).encode()), server_ip_port)
    # # OK 111
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("c" * 1000).encode()), server_ip_port)
    # # OK 1011
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("d" * 1459).encode()), server_ip_port)
    # # OK 1470
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("e" * 1460).encode()), server_ip_port)
    # # OK 1471
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("f" * 1461).encode()), server_ip_port)
    # # OK 1472
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("g" * 1462).encode()), server_ip_port)
    # # NOK 1473 - fragmentovane na linkovej vrstve
    # klient_socket.sendto(vytvor_datovy_paket(poradove_cislo, velkost_dat, ("h" * 1463).encode()), server_ip_port)
    # # NOK 1473 - fragmentovane na linkovej vrstve


    # klient_socket.sendto(b"", server_ip_port)


def klient_vysielac_subor(klient_socket, server_ip_port, fragment_velkost):
    # C:\Users\PeterSmrecek\Desktop\Odosielanie\Dummy.txt

    cesta = input("Zadaj cestu k suboru: ")
    nazov_suboru = os.path.basename(cesta)
    dlzka_dat = len(nazov_suboru)
    paket_s_nazvom = vytvor_datovy_paket(0, dlzka_dat, nazov_suboru.encode(), b"d")
    klient_socket.sendto(paket_s_nazvom, server_ip_port)

    subor = open(cesta, "rb")
    data = subor.read()

    pole_fragmentov = fragmentuj(data, fragment_velkost)

    ukonci_keepalive()

    poradove_cislo = 1
    for fragment in pole_fragmentov[:-1]:
        velkost_dat = len(fragment)
        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, b"e")
        klient_socket.sendto(paket, server_ip_port)
        poradove_cislo += 1
    fragment = pole_fragmentov[-1]
    velkost_dat = len(fragment)
    paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, b"f")
    klient_socket.sendto(paket, server_ip_port)

    spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
    return


def main():
    zaciatok_funkcie(main.__name__, True)

    rezim = input("Zvol s pre server, zvol k pre klient, zvol x pre skoncenie programu: ")
    while rezim != "x":
        if rezim == "s":
            server_riadic()
        elif rezim == "k":
            klient_riadic()
        else:
            print("Nespravna volba")
        rezim = input("Zvol s pre server, zvol k pre klient, zvol x pre skoncenie programu: ")


    # bytes = (1024).to_bytes(2, 'big', signed=False)
    # cislo = int.from_bytes(bytes, byteorder='big', signed=False)
    # print(bytes, cislo)

    # # cesta = input()
    # # print(cesta)
    # # cesta = r"C:\Users\PeterSmrecek\Desktop\Odosielanie\Lorem ipsum.txt"
    # cesta = r"C:\Users\PeterSmrecek\Desktop\Odosielanie\Dummy.txt"
    # # print(cesta)
    # # cesta = os.path.normpath(cesta)
    # # print(cesta)
    # print(os.path.basename(cesta))
    # file = open(cesta, "rb")
    # # for line in file:
    # #     print(line)
    # fragment = file.read(2)
    # print(fragment)
    # fragment = file.read(2)
    # print(fragment)
    # fragment = file.read(2)
    # print(fragment)
    # fragment = file.read(2)
    # print(fragment)
    # file.close()

    zaciatok_funkcie(main.__name__, False)


if __name__ == "__main__":
    main()
