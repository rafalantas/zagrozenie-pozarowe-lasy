import requests
from bs4 import BeautifulSoup
from discord_webhook import DiscordWebhook, DiscordEmbed
import os
import re

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
IMG_URL = "https://www.traxelektronik.pl/pogoda/las/img/18_0map.png"
DATA_URL = "https://www.traxelektronik.pl/pogoda/las/rejon.php?RejID=18"
IMG_FILE = "18_0map.png"
STACJA_ID = "622"

KOLORY_ZAGROZENIA = {
    "0": 0x2ECC71,   # zielony      – brak
    "1": 0xF1C40F,   # żółty        – małe
    "2": 0xE67E22,   # pomarańczowy – średnie
    "3": 0xE74C3C,   # czerwony     – duże
}

EMOJI_ZAGROZENIA = {
    "0": "🟢",
    "1": "🟡",
    "2": "🟠",
    "3": "🔴",
}

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
        soup = BeautifulSoup(response.content, "html.parser", from_encoding="iso-8859-2")

        # Znajdź wiersz Hajnówki po ID stacji
        link = soup.find('a', href=re.compile(rf'idst={STACJA_ID}'))
        dane_hajnowka = None
        if link:
            row = link.find_parent('tr')
            if row:
                cols = row.find_all('td')
                if len(cols) >= 5:
                    def pierwsza_liczba(td):
                        for s in td.strings:
                            s = s.strip().replace('*', '')
                            if re.match(r'^-?\d+(\.\d+)?$', s):
                                return s
                        return 'brak'

                    dane_hajnowka = {
                        "stacja":         link.get_text(strip=True),
                        "wilg_sciolka":   pierwsza_liczba(cols[1]),
                        "suma_opadu":     pierwsza_liczba(cols[2]),
                        "wilg_powietrze": pierwsza_liczba(cols[3]),
                        "temp_powietrze": pierwsza_liczba(cols[4]),
                    }

        # Stopień zagrożenia dla strefy 1_E
        zagrozenie = None
        for td in soup.find_all('td', attrs={'colspan': '6'}):
            text = td.get_text(separator=' ', strip=True)
            if '1_E' in text and 'SZPL' in text:
                match = re.search(r'SZPL\s*:\s*(\d+\s*-\s*zagro\S+\s+\S+)', text)
                if match:
                    zagrozenie = match.group(1).strip()
                else:
                    zagrozenie = text.split(':')[-1].strip()
                break

        # Godzina danych
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

def wyslij_na_discord(title, opis, kolor, obrazek=None):
    try:
        webhook = DiscordWebhook(url=WEBHOOK_URL)
        embed = DiscordEmbed(title=title, description=opis, color=kolor)
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
        czas = f"\nDane z {godzina}" if godzina else ""
        zag  = zagrozenie if zagrozenie else "brak danych"

        poziom = re.match(r'^(\d)', zag)
        poziom = poziom.group(1) if poziom else "0"
        kolor  = KOLORY_ZAGROZENIA.get(poziom, 0x95A5A6)
        emoji  = EMOJI_ZAGROZENIA.get(poziom, "⚪")

        title = f"{emoji} Zagrożenie pożarowe lasu – Hajnówka"
        opis  = (
            f"**{zag}**{czas}\n"
            f"\n"
            f"🌿 Wilgotność ściółki: **{dane['wilg_sciolka']}%**\n"
            f"🌧️ Suma opadu: **{dane['suma_opadu']} mm**\n"
            f"💧 Wilgotność powietrza: **{dane['wilg_powietrze']}%**\n"
            f"🌡️ Temperatura powietrza: **{dane['temp_powietrze']}°C**"
        )
    else:
        title = "⚠️ Hajnówka – brak danych"
        opis  = "Nie znaleziono danych dla stacji Hajnówka."
        kolor = 0x95A5A6

    wyslij_na_discord(title, opis, kolor, IMG_FILE if pobrano_obrazek else None)

if __name__ == "__main__":
    main()
