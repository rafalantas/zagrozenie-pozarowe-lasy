import requests
from bs4 import BeautifulSoup
from discord_webhook import DiscordWebhook, DiscordEmbed
import os
import re

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
        # strona kodowana w ISO-8859-2
        soup = BeautifulSoup(response.content, "html.parser", from_encoding="iso-8859-2")

        # Parsowanie danych dla Hajnówki
        dane_hajnowka = None
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 5 and "Hajn" in cols[0].get_text():
                # wartości są bezpośrednio jako tekst w td, obok linka
                def val(td):
                    # usuń tagi <a> i <span>, zostaw tylko teksty
                    for tag in td.find_all(['a', 'span']):
                        tag.decompose()
                    t = td.get_text(strip=True).replace('*', '').replace('-', 'brak')
                    return t if t else 'brak'

                dane_hajnowka = {
                    "stacja":         "Hajnówka",
                    "wilg_sciolka":   val(cols[1]),
                    "suma_opadu":     val(cols[2]),
                    "wilg_powietrze": val(cols[3]),
                    "temp_powietrze": val(cols[4]),
                }
                break

        # Parsowanie stopnia zagrożenia dla strefy 1_E
        zagrozenie = None
        for td in soup.find_all('td', attrs={'colspan': '6'}):
            text = td.get_text(separator=' ', strip=True)
            if '1_E' in text and 'SZPL' in text:
                match = re.search(r'SZPL\s*:\s*(\d+\s*-\s*zagro.enie\s+\S+)', text)
                if match:
                    zagrozenie = match.group(1).strip()
                else:
                    zagrozenie = text.split(':')[-1].strip()
                break

        # Parsowanie godziny
        godzina = None
        for tag in soup.find_all(string=re.compile(r'zosta. wyznaczony na podstawie danych z')):
            raw = tag.parent.get_text(separator=' ', strip=True)
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', raw)
            if match:
                godzina = match.group(1)
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

    if dane:
        czas = f" Dane z {godzina}" if godzina else ""
        zag  = zagrozenie if zagrozenie else "brak danych"
        wiadomosc = (
            f"Hajnówka – zagrożenie pożarowe lasu: {zag}.{czas}\n"
            f"Stacja: {dane['stacja']}\n"
            f"Wilgotność ściółki: {dane['wilg_sciolka']}%\n"
            f"Suma opadu: {dane['suma_opadu']} mm\n"
            f"Wilgotność powietrza: {dane['wilg_powietrze']}%\n"
            f"Temperatura powietrza: {dane['temp_powietrze']}°C"
        )
    else:
        wiadomosc = "Nie znaleziono danych dla Hajnówki."

    wyslij_na_discord(wiadomosc, IMG_FILE if pobrano_obrazek else None)

if __name__ == "__main__":
    main()
