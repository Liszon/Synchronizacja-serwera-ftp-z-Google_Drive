import funkcje

id_folderu_glownego_google_drive = 'ID Folderu ktory chcemy synchronizowac na serwerze FTP'

# definiowanie ustawien serwera ftp
host = 'Host serwera FTP'
user = 'uzytkownik FTP'
passwd = 'Haslo FTP'
path_folder_glowny_ftp = 'Sciezka do folderu w ktorym chcemy przechowywac pliki z Dysku Googla'

# dane dotyczace wysylania maili z bledami
nadawca = 'Email nadawcy'
haslo_nadawcy = 'Haslo do maila nadawcy'
odbiorca = 'Email odbiorcy'


funkcje.synchronizacja(path_folder_glowny_ftp, id_folderu_glownego_google_drive, host, user, passwd, nadawca, haslo_nadawcy, odbiorca)

'''
Plik main w tym programie sluzy jako plik konfiguracyjny
Ustawiamy w nim wszystkie zmienne dotyczace dysku googla jak, serwera FTP jak i emaili
Wyjatek stanowia foldery znajdujace sie w synchronizowanym przez nas dysku googla, a ktorych nie chcemy miec na dysku
FTP
Wykluczenia folderow znajduja sie w pliku funkcje.py w linijce [57] gdzie nalezy dodac wpis do query 
"and not 'id niechcianego folderu' in parents"


Do poprawnego dzialanie programu niezbedny jest takze plik client_secrets.json generowany za pomoca Google Cloud
Jego nazwe nalezy zmienic na credentials.json
'''