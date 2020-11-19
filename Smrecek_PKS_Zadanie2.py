import socket
import struct
import crcmod
import sys

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

crc32_func = crcmod.mkCrcFun(0x104c11db7, initCrc=0, xorOut=0xFFFFFFFF)


def vytvor_datovy_paket(poradove_cislo, velkost_dat, data, chyba = False):
    crc = 0
    flag = b'0'
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

    data1, addr1 = server_socket.recvfrom(1500)
    otvorenie = False
    if data1 == b"OTVORENIE SPOJENIA K->S":
        print("SERVER - Prijatie otvorenia spojenia z adresy {}".format(addr1))
        server_socket.sendto(b"OTVORENIE SPOJENIA S->K", addr1)
        otvorenie = True
    else:
        print("SERVER - Odmietnutie otvorenia spojenia z adresy {}".format(addr1))
        server_socket.sendto(b"ZAMIETNUTIE SPOJENIA S->K", addr1)

    data2, addr2 = server_socket.recvfrom(1500)
    if data2 == b"POTVRDENIE SPOJENIA K->S" and addr1 == addr2 and otvorenie:
        print("SERVER - Prijatie potvrdenia spojenia z adresy {}".format(addr1))
        print("SERVER - Spojenie s {} bolo uspesne nadviazane".format(addr1))
    else:
        print("SERVER - Prijatie zamietnutia spojenia z adresy {}".format(addr1))
        print("SERVER - Zatvaram spojenie")
        server_socket.close()

    server_prijimac(server_socket, addr1)
    server_socket.close()


def server_prijimac(server_socket, addr):

    while True:
        paket, addr = server_socket.recvfrom(1500)
        if len(paket) == 0:
            break
        poradove_cislo, velkost_dat, flag, data, chyba = rozbal_datovy_paket(paket)
        print(poradove_cislo, velkost_dat, flag, chyba, data.decode("utf-8"))


def klient_riadic():
    ip_adresa_servera = input("KLIENT - Zadaj IP adresu servera: ")
    port = int(input("KLIENT - Zadaj port: "))
    # ip_adresa_servera = "127.0.0.1"
    # port = 1234
    print("KLIENT - Zvolena IP adresa servera", ip_adresa_servera)
    print("KLIENT - Zvoleny port", port)

    server_ip_port = (ip_adresa_servera, port)

    klient_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # klient_socket.bind(('', port))
    # klient_socket.sendto(''.encode(), server_ip_port)
    # klient_socket.connect(server_ip_port)

    klient_socket.sendto(b"OTVORENIE SPOJENIA K->S", server_ip_port)
    data, addr = klient_socket.recvfrom(1500)
    if addr == server_ip_port and data == b"OTVORENIE SPOJENIA S->K":
        print("KLIENT - Spojenie so serverom {} bolo uspesne nadviazane".format(addr))
        klient_socket.sendto(b"POTVRDENIE SPOJENIA K->S", addr)
    else:
        print("KLIENT - Spojenie so serverom {} bolo zamietnute serverom".format(addr))
        print("KLIENT - Zatvaram spojenie")
        klient_socket.sendto(b"POTVRDENIE SPOJENIA K->S", addr)
        klient_socket.close()
        return

    klient_vysielac(klient_socket, server_ip_port)
    klient_socket.close()


def klient_vysielac(klient_socket, server_ip_port):

    sprava = input("Zadaj spravu na odoslanie: ")

    while sprava != "":
        poradove_cislo = 0
        data = sprava.encode()
        velkost_dat = len(data)
        paket = vytvor_datovy_paket(poradove_cislo, velkost_dat, data)

        klient_socket.sendto(paket, server_ip_port)

        sprava = input("Zadaj spravu na odoslanie: ")

    klient_socket.sendto(b"", server_ip_port)


def main():
    zaciatok_funkcie(main.__name__, True)

    # print(MAX_SIZE_ON_WIRE)

    rezim = input("Zvol s pre server, zvol k pre klient: ")

    if rezim == "s":
        server_riadic()
    elif rezim == "k":
        klient_riadic()
    else:
        print("Nespravna volba")

    # data = b'abcde'
    # paket = vytvor_datovy_paket(0, len(data), data, chyba=False)
    # print(rozbal_datovy_paket(paket))

    zaciatok_funkcie(main.__name__, False)


if __name__ == "__main__":
    main()
