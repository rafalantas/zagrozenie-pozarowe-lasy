import requests
from bs4 import BeautifulSoup
from discord_webhook import DiscordWebhook, DiscordEmbed
import os

# Konfiguracja
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
IMG_URL = "https://www.traxelektronik.pl/pogoda/las/img/18_0map.png"
DATA_URL = "https://www.traxelektronik.pl/pogoda/las/rejon.php?RejID=18"
IMG_FILE = "18_0map.png"

def pobierz_i_zapisz_obrazek():
    try:
        response = requests.get(IMG_URL)
        if response.status_code == 200:
            with open(IMG_FILE, "wb") as f:
                f.write(response.content)
            return True
        return False
    except Exception as e:
        print(f"Błąd pobierania obrazka: {e}")
        return False

def pobierz_dane_i_zagrozenie_i_godzine():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(DATA_URL, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        dane_hajnowka = None
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 5 and "Hajnówka" in cols[0].get_text(strip=True):
                dane_hajnowka = {
                    "stacja": cols[0].get_text(strip=True),
                    "wilg_sciolka": cols[1].get_text(strip=True),
                    "suma_opadu": cols[2].get_text(strip=True),
                    "wilg_powietrze": cols[3].get_text(strip=True),
                    "temp_powietrze": cols[4].get_text(strip=True)
                }
                break

        zagrozenie = None
        for td in soup.find_all('td', attrs={'colspan': '6'}):
            text = td.get_text(separator=' ', strip=True)
            if 'strefa 1_E' in text and 'SZPL' in text:
                zagrozenie = text.split(':')[-1].strip()
                break

        godzina = None
        for tag in soup.find_all():
            if tag.text and "został wyznaczony na podstawie danych z" in tag.text:
                godzina = tag.text.split("został wyznaczony na podstawie danych z")[-1].strip().split('.')[0].strip()
                break

        return dane_hajnowka, zagrozenie, godzina
    except Exception as e:
        print(f"Błąd pobierania danych: {e}")
        return None, None, None

def wyslij_na_discord(wiadomosc, obrazek=None):
    try:
        webhook = DiscordWebhook(url=WEBHOOK_URL)
        embed = DiscordEmbed(description=wiadomosc)
        webhook.add_embed(embed)
        if obrazek and os.path.exists(obrazek):
            with open(obrazek, "rb") as f:
                webhook.add_file(file=f.read(), filename=obrazek)
        webhook.execute()
    except Exception as e:
        print(f"Błąd wysyłania na Discord: {e}")

def main():
    pobrano_obrazek = pobierz_i_zapisz_obrazek()
    dane, zagrozenie, godzina = pobierz_dane_i_zagrozenie_i_godzine()

    if dane and zagrozenie and godzina:
        wiadomosc = (
            f"Hajnówka – zagrożenie pożarowe lasu: {zagrozenie}. Dane z {godzina}\n"
            f"Stacja: {dane['stacja']}\n"
            f"Wilgotność ściółki: {dane['wilg_sciolka']}%\n"
            f"Suma opadu: {dane['suma_opadu']} mm\n"
            f"Wilgotność powietrza: {dane['wilg_powietrze']}%\n"
            f"Temperatura powietrza: {dane['temp_powietrze']}°C"
        )
    elif dane and zagrozenie:
        wiadomosc = (
            f"Hajnówka – zagrożenie pożarowe lasu: {zagrozenie}\n"
            f"Stacja: {dane['stacja']}\n"
            f"Wilgotność ściółki: {dane['wilg_sciolka']}%\n"
            f"Suma opadu: {dane['suma_opadu']} mm\n"
            f"Wilgotność powietrza: {dane['wilg_powietrze']}%\n"
            f"Temperatura powietrza: {dane['temp_powietrze']}°C"
        )
    elif dane:
        wiadomosc = (
            f"Hajnówka – zagrożenie pożarowe lasu: brak danych\n"
            f"Stacja: {dane['stacja']}\n"
            f"Wilgotność ściółki: {dane['wilg_sciolka']}%\n"
            f"Suma opadu: {dane['suma_opadu']} mm\n"
            f"Wilgotność powietrza: {dane['wilg_powietrze']}%\n"
            f"Temperatura powietrza: {dane['temp_powietrze']}°C"
        )
    else:
        wiadomosc = "Nie znaleziono danych dla Hajnówki ani stopnia zagrożenia."

    wyslij_na_discord(wiadomosc, IMG_FILE if pobrano_obrazek else None)

if __name__ == "__main__":
    main()
