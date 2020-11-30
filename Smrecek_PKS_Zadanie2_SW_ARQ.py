import socket
import struct
import crcmod
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
UKONCI = []
AKTIVNY_SERVER = False

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


def vytvor_hlavicku(poradove_cislo, crc, spojena_velkost, flag):
    hlavicka = b""
    hlavicka += poradove_cislo.to_bytes(4, 'big', signed=False)
    hlavicka += crc.to_bytes(4, 'big', signed=False)
    hlavicka += spojena_velkost.to_bytes(2, 'big', signed=False)
    hlavicka += flag

    return hlavicka


def rozbal_hlavicku(hlavicka):
    poradove_cislo = int.from_bytes(hlavicka[0:4], byteorder='big', signed=False)
    crc = int.from_bytes(hlavicka[4:8], byteorder='big', signed=False)
    celkova_velkost = int.from_bytes(hlavicka[8:10], byteorder='big', signed=False)
    # flag = int.from_bytes(hlavicka[10:11], byteorder='big', signed=False)
    flag = hlavicka[10:11]

    return poradove_cislo, crc, celkova_velkost, flag


def vytvor_datovy_paket(poradove_cislo, velkost_dat, data, flag, chyba=False):
    crc = 0

    hlavicka = vytvor_hlavicku(poradove_cislo, crc, velkost_dat + VELKOST_HLAVICKY_DAT, flag)
    crc = crc32_func(hlavicka + data)
    if chyba:
        crc -= 1

    hlavicka = vytvor_hlavicku(poradove_cislo, crc, velkost_dat + VELKOST_HLAVICKY_DAT, flag)
    vysledok = hlavicka + data

    return vysledok


def rozbal_datovy_paket(paket):
    poradove_cislo, crc, celkova_velkost, flag = rozbal_hlavicku(paket[:VELKOST_HLAVICKY_DAT])
    data = paket[VELKOST_HLAVICKY_DAT:]
    hlavicka = vytvor_hlavicku(poradove_cislo, 0, celkova_velkost, flag)
    kontrolne_crc = crc32_func(hlavicka + data)
    if kontrolne_crc == crc:
        chyba = False
    else:
        chyba = True
    velkost_dat = celkova_velkost - VELKOST_HLAVICKY_DAT
    return poradove_cislo, velkost_dat, flag, data, chyba


def server_riadic():
    port = int(input("SERVER - Zadaj port: "))
    # port = 1234
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

    server_prijimac(server_socket, addr)
    print("SERVER - odhlasenie")
    server_socket.close()


def zbal_potvrdzujuce_cislo(cislo_poskodeneho):
    # data = b""
    # for cislo in pole_poskodenych:
    #     bajty = cislo.to_bytes(4, 'big', signed=False)
    #     data += bajty

    data = cislo_poskodeneho.to_bytes(4, 'big', signed=False)

    return data


def server_prijimac(server_socket, addr):

    slovnik_fragmentov = {}
    celkovy_pocet_fragmentov = -2

    datove_flagy = b"bcef"
    textova_sprava = True

    cislo_potvrdzovacej_spravy = 1
    cislo_keepalive = 1
    celkovy_pocet_paketov = 1

    server_socket.settimeout(3 * KEEPALIVE_INTERVAL)
    try:
        while True:
            paket, addr = server_socket.recvfrom(1500)
            poradove_cislo, velkost_dat, flag, data, chyba = rozbal_datovy_paket(paket)

            if flag == b"k":
                print("SERVER - {}: prijal keepalive cislo: {}, "
                      "velkost dat: {}, flag: {}, chyba: {}".format(celkovy_pocet_paketov, poradove_cislo, velkost_dat,
                                                                    flag, chyba))
                celkovy_pocet_paketov += 1
                keepalive_paket = vytvor_datovy_paket(cislo_keepalive, 0, b"", b"k")
                server_socket.sendto(keepalive_paket, addr)
                cislo_keepalive += 1
                continue

            if flag not in datove_flagy:
                print("SERVER - {}: prijal signalizacnu spravu cislo: {}, "
                      "velkost dat: {}, flag: {}, chyba: {}".format(celkovy_pocet_paketov, poradove_cislo, velkost_dat,
                                                                    flag, chyba))
            else:
                print("SERVER - {}: prijal fragment cislo: {}, "
                    "velkost dat: {}, flag: {}, chyba: {}".format(celkovy_pocet_paketov, poradove_cislo, velkost_dat,
                                                                  flag, chyba))
            celkovy_pocet_paketov += 1
            if flag in datove_flagy:
                potvrdzujuce_cislo = zbal_potvrdzujuce_cislo(poradove_cislo)
                if chyba:
                    potvrdzovaci_paket = vytvor_datovy_paket(cislo_potvrdzovacej_spravy, len(potvrdzujuce_cislo), potvrdzujuce_cislo, b"n")
                else:
                    potvrdzovaci_paket = vytvor_datovy_paket(cislo_potvrdzovacej_spravy, len(potvrdzujuce_cislo), potvrdzujuce_cislo, b"a")
                    slovnik_fragmentov[poradove_cislo] = data
                server_socket.sendto(potvrdzovaci_paket, addr)

            if flag == b"d":
                slovnik_fragmentov[poradove_cislo] = data

            if flag == b"g":
                print("SERVER - klient ukoncil spojenie")
                break

            if flag == b"d" or flag == b"e" or flag == b"f":
                textova_sprava = False

            if flag == b"c" or flag == b"f":
                celkovy_pocet_fragmentov = poradove_cislo

            if textova_sprava:
                if len(slovnik_fragmentov) == celkovy_pocet_fragmentov:
                    sprava = b""
                    for i in range(1, celkovy_pocet_fragmentov + 1):
                        sprava += slovnik_fragmentov[i]
                    print("SERVER - cele znenie spravy:")
                    print(sprava.decode("utf-8"))
                    slovnik_fragmentov.clear()
                    celkovy_pocet_fragmentov = -2
                    if chcem_skoncit():
                        return
            elif len(slovnik_fragmentov) == celkovy_pocet_fragmentov + 1:
                nazov_suboru = slovnik_fragmentov[0].decode("utf-8")
                while True:
                    try:
                        priecinok = input("Zadaj cestu k priecinku, kde ma byt subor {} ulozeny: ".format(nazov_suboru))
                        cesta = os.path.join(priecinok, nazov_suboru)
                        subor = open(cesta, "wb")
                        break
                    except:
                        print("Zadana nespravna cesta")

                for i in range(1, celkovy_pocet_fragmentov + 1):
                    subor.write(slovnik_fragmentov[i])
                subor.close()
                print("Cesta k suboru je:", cesta)
                slovnik_fragmentov.clear()
                celkovy_pocet_fragmentov = -2
                textova_sprava = True
                if chcem_skoncit():
                    return

    except socket.timeout:
        print("SERVER - ukoncenie spojenia z dovodu neaktivity klienta")


def posli_keepalive(klient_socket, server_ip_port, cas, ka_id):
    print("KLIENT - posielanie keepalive spustene")
    cislo_keepalive = 1

    chybajuce = 0

    while True:
        global UKONCI
        if UKONCI[ka_id]:
            return

        paket = vytvor_datovy_paket(cislo_keepalive, 0, b"", b"k")
        klient_socket.sendto(paket, server_ip_port)
        cislo_keepalive += 1
        print("KLIENT - poslal som keepalive")

        global AKTIVNY_SERVER

        klient_socket.settimeout(KEEPALIVE_INTERVAL)
        try:
            data, addr = klient_socket.recvfrom(1500)
            poradove_cislo, velkost_dat, flag, data, chyba = rozbal_datovy_paket(data)
            if flag == b"k":
                chybajuce = 0
                print("KLIENT - prijal keepalive cislo: {}, "
                      "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))
                time.sleep(cas)
            else:
                chybajuce += 1
        except socket.timeout:
            chybajuce += 1
            print("KLIENT - odpoved na keepalive neprisla v stanovenom case")
        except ConnectionResetError:
            print("KLIENT - vypnuty server")
            AKTIVNY_SERVER = False
            return

        if chybajuce == 3:
            print("KLIENT - server neaktivny")
            AKTIVNY_SERVER = False
            return


def spusti_keepalive(klient_socket, server_ip_port, cas):
    ukonci_keepalive()
    global UKONCI
    ka_id = len(UKONCI)
    UKONCI.append(False)

    thread = threading.Thread(target=posli_keepalive, args=(klient_socket, server_ip_port, cas, ka_id))
    thread.daemon = True

    thread.start()


def ukonci_keepalive():
    global UKONCI
    if sum(UKONCI) > 0:
        print("KLIENT - posielanie keepalive zastavene")
    UKONCI = [True for i in range(len(UKONCI))]


def klient_riadic():
    ip_adresa_servera = input("KLIENT - Zadaj IP adresu servera: ")
    print("KLIENT - zadaj port: ", end="")
    port = nacitaj_cislo(1024, 49151)

    # ip_adresa_servera = "127.0.0.1"
    # port = 1234
    print("KLIENT - Zvolena IP adresa servera", ip_adresa_servera)
    print("KLIENT - Zvoleny port", port)

    server_ip_port = (ip_adresa_servera, port)

    klient_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    inicializacny_paket = vytvor_datovy_paket(0, 0, b"", b"a")
    try:
        klient_socket.sendto(inicializacny_paket, server_ip_port)
    except OSError:
        print("KLIENT - na zvolenu IP sa nepodarilo odoslat spravu")
        print("KLIENT - Zatvaram spojenie")
        klient_socket.close()
        return

    try:
        data, addr = klient_socket.recvfrom(1500)
    except OSError:
        print("KLIENT - server neaktivny")
        print("KLIENT - Zatvaram spojenie")
        klient_socket.close()
        return

    rozbalene = rozbal_datovy_paket(data)
    if addr == server_ip_port and rozbalene[2] == b"a":
        print("KLIENT - Spojenie so serverom {} bolo uspesne nadviazane".format(addr))
    else:
        print("KLIENT - Spojenie so serverom {} bolo zamietnute serverom".format(addr))
        print("KLIENT - Zatvaram spojenie")
        klient_socket.close()
        return

    global AKTIVNY_SERVER
    AKTIVNY_SERVER = True

    volba = "Zadaj t pre odoslanie textovej spravy, zadaj s pre odoslanie suboru, zadaj x pre odhlasenie, " \
            "zadaj on pre spustenie keepalive, zadaj off pre ukoncenie posielania sprav keepalive: "
    rezim = input(volba)
    while rezim != "x":
        if rezim == "t":
            if AKTIVNY_SERVER:
                ukonci_keepalive()
                print("Zadaj velkost datoveho fragmentu")
                fragment_velkost = nacitaj_cislo(MIN_DATA_SIZE, MAX_DATA_SIZE)
                klient_vysielac_text(klient_socket, server_ip_port, fragment_velkost)
                spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
            else:
                print("KLIENT - neaktivny server, odhlaste sa")
        elif rezim == "s":
            if AKTIVNY_SERVER:
                ukonci_keepalive()
                print("Zadaj velkost datoveho fragmentu")
                fragment_velkost = nacitaj_cislo(MIN_DATA_SIZE, MAX_DATA_SIZE)
                klient_vysielac_subor(klient_socket, server_ip_port, fragment_velkost)
                spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
            else:
                print("KLIENT - neaktivny server, odhlaste sa")
        elif rezim == "on":
            spusti_keepalive(klient_socket, server_ip_port, KEEPALIVE_INTERVAL)
        elif rezim == "off":
            ukonci_keepalive()
        else:
            print("Nespravna volba")
        time.sleep(1)
        rezim = input(volba)

    ukonci_keepalive()
    ukoncovaci_paket = vytvor_datovy_paket(0, 0, b"", b"g")
    print("KLIENT - odosielanie spravy pre ukoncenie spojenia")
    klient_socket.sendto(ukoncovaci_paket, server_ip_port)
    print("KLIENT - odhlasenie")

    klient_socket.close()


def rozbal_potvrdzujuce_cislo(data):
    n = 4
    cislo = int.from_bytes(data, byteorder='big', signed=False)
    return cislo


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


def retransmisia_sw(klient_socket, server_ip_port, poradove_cislo, velkost_dat, fragment, flag, chyba):
    potvrdzujuce_flagy = b"an"
    ack = False
    klient_socket.settimeout(5)
    while not ack:
        try:
            data2, addr2 = klient_socket.recvfrom(1500)
            rozbalene = rozbal_datovy_paket(data2)
            potvrdzujuci_flag = rozbalene[2]
            potvrdzujuce_cislo = rozbal_potvrdzujuce_cislo(
                rozbalene[3]) if potvrdzujuci_flag in potvrdzujuce_flagy else -1
            while not ack:
                if potvrdzujuce_cislo == poradove_cislo:
                    if potvrdzujuci_flag == b"n":
                        print("KLIENT - prijata negativna potvrdzujuca sprava, zacina retransmisia fragmentu ",
                              potvrdzujuce_cislo)
                        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag)
                        klient_socket.sendto(paket, server_ip_port)
                        print("KLIENT - opatovne odoslal fragment cislo: {}, "
                              "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag,
                                                                            chyba))
                    elif potvrdzujuci_flag == b"a":
                        print("KLIENT - prijata pozitivna potvrdzujuca sprava pre fragment ", potvrdzujuce_cislo)
                        ack = True
                        break
                    else:
                        print("KLIENT - Prisla sprava so spravnym poradovym cislom, ale nespravnym flagom")
                else:
                    print("KLIENT - prijata sprava nebola ocakavana")
                data2, addr2 = klient_socket.recvfrom(1500)
                rozbalene = rozbal_datovy_paket(data2)
                potvrdzujuci_flag = rozbalene[2]
                potvrdzujuce_cislo = rozbal_potvrdzujuce_cislo(
                    rozbalene[3]) if potvrdzujuci_flag in potvrdzujuce_flagy else -1
        except socket.timeout:
            print("KLIENT - potvrdenie zo servra neprislo vcas, opatovne odosielam fragment", poradove_cislo)
            paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag)
            klient_socket.sendto(paket, server_ip_port)
        except ConnectionResetError:
            print("KLIENT - server je neaktivny")
            global AKTIVNY_SERVER
            AKTIVNY_SERVER = False
            return False
    return True


def chcem_chybu():
    while True:
        vstup = input("Zadaj a pre vlozenie chyby, zadaj n pre nevlozenie chyby: ")
        if vstup == "a":
            return True
        if vstup == "n":
            return False
        print("Nespravny vstup")


def chcem_skoncit():
    while True:
        vstup = input("Zadaj o pre odhlasenie, zadaj p pre pokracovanie: ")
        if vstup == "o":
            return True
        if vstup == "p":
            return False
        print("Nespravny vstup")


def klient_vysielac_text(klient_socket, server_ip_port, fragment_velkost):

    sprava = input("Zadaj spravu na odoslanie: ")

    chyba = chcem_chybu()
    if chyba:
        print("KLIENT - chyba bude vlozena do prveho fragmentu textu")

    data = sprava.encode()
    pole_fragmentov = fragmentuj(data, fragment_velkost)

    poradove_cislo = 1
    flag = b"b"

    for fragment in pole_fragmentov[:-1]:
        velkost_dat = len(fragment)
        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag, chyba)
        chyba = False
        klient_socket.sendto(paket, server_ip_port)
        print("KLIENT - odoslal fragment cislo: {}, "
              "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))

        if not retransmisia_sw(klient_socket, server_ip_port, poradove_cislo, velkost_dat, fragment, flag, chyba):
            return

        poradove_cislo += 1

    fragment = pole_fragmentov[-1]
    velkost_dat = len(fragment)
    flag = b"c"
    paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag, chyba)
    klient_socket.sendto(paket, server_ip_port)
    print("KLIENT - odoslal fragment cislo: {}, "
          "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))

    if not retransmisia_sw(klient_socket, server_ip_port, poradove_cislo, velkost_dat, fragment, flag, chyba):
        return

    return


def klient_vysielac_subor(klient_socket, server_ip_port, fragment_velkost):

    data = b""

    while True:
        try:
            cesta = input("Zadaj cestu k suboru: ")
            subor = open(cesta, "rb")
            data = subor.read()
            break
        except:
            print("Subor nebol najdeny")

    chyba = chcem_chybu()
    if chyba:
        print("KLIENT - chyba bude vlozena do prveho fragmentu suboru, ktory sa prenesie po prenose nazvu suboru")

    nazov_suboru = os.path.basename(cesta)
    dlzka_nazvu = len(nazov_suboru)
    paket_s_nazvom = vytvor_datovy_paket(0, dlzka_nazvu, nazov_suboru.encode(), b"d")
    klient_socket.sendto(paket_s_nazvom, server_ip_port)

    pole_fragmentov = fragmentuj(data, fragment_velkost)

    poradove_cislo = 1
    flag = b"e"

    for fragment in pole_fragmentov[:-1]:
        velkost_dat = len(fragment)
        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag, chyba)
        chyba = False
        klient_socket.sendto(paket, server_ip_port)
        print("KLIENT - odoslal fragment cislo: {}, "
              "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))

        if not retransmisia_sw(klient_socket, server_ip_port, poradove_cislo, velkost_dat, fragment, flag, chyba):
            return

        poradove_cislo += 1

    fragment = pole_fragmentov[-1]
    velkost_dat = len(fragment)
    flag = b"f"
    paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, fragment, flag, chyba)
    klient_socket.sendto(paket, server_ip_port)
    print("KLIENT - odoslal fragment cislo: {}, "
          "velkost dat: {}, flag: {}, chyba: {}".format(poradove_cislo, velkost_dat, flag, chyba))

    if not retransmisia_sw(klient_socket, server_ip_port, poradove_cislo, velkost_dat, fragment, flag, chyba):
        return

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

    zaciatok_funkcie(main.__name__, False)


if __name__ == "__main__":
    main()
