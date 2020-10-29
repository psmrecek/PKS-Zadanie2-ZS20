

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


def main():
    zaciatok_funkcie(main.__name__, True)


    zaciatok_funkcie(main.__name__, False)


if __name__ == "__main__":
    main()
