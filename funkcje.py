from ftputil.error import FTPOSError
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from Google import Create_Service
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import io
import os
import pickle
import sys
import ftputil
import ftputil.session
import errno
import shutil

CLIENT_SECRET_FILE = 'credentials.json'
API_NAME = 'drive'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/drive']

service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

'''
-----------------------------------Spis Tresci-----------------------------------   - linijka
Sekcja funkcji odpowiedzialnych za pobieranie i wysylanie                           - 37
Sekcja funkcji odpowiedzialnych za listing plikow i folderow w google drive i FTP   - 192
Sekcja funkcji odpowiedzialnej za wysylanie wiadomosci na adres email               - 290
Sekcja funkcji odpowiedzlanych za  usuwanie plikow i folderow na serwezre FTP       - 310
Funkcja ktora zbiera w calosc funkcje do pobieranie i wysylania                     - 384
Glowna funkcja programu                                                             - 413
'''


def download(folder_name, location):
    bledy = []
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=1337)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token, protocol=0)
    service = build('drive', 'v3', credentials=creds)

    if location[-1] != '/':
        location += '/'

    folder = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
        fields='files(id, name, parents, trashed)').execute()

    total = len(folder['files'])
    if total != 1:
        print(f'{total} folders found')
        if total == 0:
            sys.exit(1)
        prompt = 'Please select the folder you want to download:\n\n'
        for i in range(total):
            prompt += f'[{i}]: {get_full_path(service, folder["files"][i])}\n'
        prompt += '\nYour choice: '
        choice = int(input(prompt))
        if 0 <= choice < total:
            folder_id = folder['files'][choice]['id']
            folder_name = folder['files'][choice]['name']
            trashed = folder['files'][choice]['trashed']
        else:
            sys.exit(1)
    else:
        folder_id = folder['files'][0]['id']
        folder_name = folder['files'][0]['name']
        trashed = folder['files'][0]['trashed']

    if trashed is False:
        print(f'{folder_id} {folder_name}')
        bledy = download_folder(service, folder_id, location, folder_name)

    return bledy


def get_full_path(service, folder):
    if not 'parents' in folder:
        return folder['name']
    files = service.files().get(fileId=folder['parents'][0], fields='id, name, parents').execute()
    path = files['name'] + ' > ' + folder['name']
    while 'parents' in files:
        files = service.files().get(fileId=files['parents'][0], fields='id, name, parents').execute()
        path = files['name'] + ' > ' + path
    return path


def download_folder(service, folder_id, location, folder_name):
    if not os.path.exists(location + folder_name):
        os.makedirs(location + folder_name)
    location += folder_name + '/'

    bledy = []
    result = []
    page_token = None
    while True:
        files = service.files().list(
            q=f"'{folder_id}' in parents",
            fields='nextPageToken, files(id, name, mimeType, shortcutDetails)',
            pageToken=page_token,
            pageSize=1000).execute()
        result.extend(files['files'])
        page_token = files.get("nextPageToken")
        if not page_token:
            break

    result = sorted(result, key=lambda k: k['name'])

    total = len(result)
    current = 1
    for item in result:
        file_id = item['id']
        filename = item['name']
        mime_type = item['mimeType']
        shortcut_details = item.get('shortcutDetails', None)
        if shortcut_details is not None:
            file_id = shortcut_details['targetId']
            mime_type = shortcut_details['targetMimeType']
        print(f'{file_id} {filename} {mime_type} ({current}/{total})')
        if mime_type == 'application/vnd.google-apps.folder':
            download_folder(service, file_id, location, filename)
        elif not os.path.isfile(location + filename):
            try:
                download_file(service, file_id, location, filename, mime_type)
            except:
                blad = 'Nie udalo sie pobrac pliku ' + filename + ' z folderu ' + location
                print(blad)
                bledy.append(blad)
        current += 1

    return bledy


def download_file(service, file_id, location, filename, mime_type):
    if 'vnd.google-apps' in mime_type:
        request = service.files().export_media(fileId=file_id,
                                               mimeType='application/pdf')
        filename += '.pdf'
    else:
        request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(location + filename, 'wb')
    downloader = MediaIoBaseDownload(fh, request, 1024 * 1024 * 1024)
    done = False
    while done is False:
        try:
            status, done = downloader.next_chunk()
        except:
            fh.close()
            os.remove(location + filename)
            sys.exit(1)
        print(f'\rDownload {int(status.progress() * 100)}%.', end='')
        sys.stdout.flush()
    print('')


def upload_dir(localDir, ftpDir, host, user, passwd):
    ftp_host = ftputil.FTPHost(host, user, passwd)
    list = os.listdir(localDir)
    ftpDirDocelowy = removeAccents(ftpDir)
    for fname in list:
        fnameDocelowy = removeAccents(fname)
        if os.path.isdir(localDir + fname):
            if not ftp_host.path.exists(ftpDirDocelowy + fnameDocelowy):
                ftp_host.mkdir(ftpDirDocelowy + fnameDocelowy)
                print(ftpDirDocelowy + fnameDocelowy + " is created.")
            upload_dir(localDir + fname + "/", ftpDir + fname + "/", host, user, passwd)
        else:
            try:
                if ftp_host.upload_if_newer(localDir + fname, ftpDirDocelowy + fnameDocelowy):
                    print(ftpDirDocelowy + fnameDocelowy + " is uploaded.")
                else:
                    print(localDir + fname + " has already been uploaded.")

            except IOError as e:
                if e.errno == errno.EPIPE:
                    exit(0)

    ftp_host.close()


def listing_nazw_folderow_gd(folder_id):
    query = f"parents = '{folder_id}'"  # parametr dzieki ktoremu przegladamy tylko wybrany folder

    response = service.files().list(q=query, fields='files(id, name, trashed, mimeType)').execute()
    files = response.get('files')
    nextPageToken = response.get('nextPageToken')

    while nextPageToken:
        response = service.files().list(q=query, fields='files(id, name, trashed, mimeType)').execute()
        files.extend(response.get('files'))
        nextPageToken = response.get('nextPageToken')

    nazwy = []
    for x in range(len(files)):
        if files[x]['mimeType'] == 'application/vnd.google-apps.folder' and files[x]['trashed'] is False:
            if ((files[x]['name'] != '_archiwum') and (
                    files[x]['name'] != '_materialy_od_klientow')):
                nazwy.append(files[x]['name'])
    return nazwy


def listing_nazw_plikow(folder_id):
    query = f"parents = '{folder_id}'"  # parametr dzieki ktoremu przegladamy tylko wybrany folder

    response = service.files().list(q=query, fields='files(id, name, trashed, mimeType)').execute()
    files = response.get('files')
    nextPageToken = response.get('nextPageToken')

    while nextPageToken:
        response = service.files().list(q=query, fields='files(id, name, trashed, mimeType)').execute()
        files.extend(response.get('files'))
        nextPageToken = response.get('nextPageToken')

    nazwy = []
    for x in range(len(files)):
        if files[x]['mimeType'] != 'application/vnd.google-apps.folder' and files[x]['trashed'] is False:
            nazwy.append(files[x]['name'])
    return nazwy


def listing_nazw_plikow_gd_bez_powtorzen(id_folderu_nadrzednego):
    lista = listing_nazw_plikow(id_folderu_nadrzednego)
    lista_bez_powtorzen = []

    for x in range(len(lista)):
        powtorzenie = False
        for y in range(len(lista_bez_powtorzen)):
            if lista[x] == lista_bez_powtorzen[y]:
                powtorzenie = True
                break
        if not powtorzenie:
            lista_bez_powtorzen.append(lista[x])

    return lista_bez_powtorzen


def listowanie_plikow_ftp(session):
    name = session.listdir(session.curdir)
    pliki = []
    for name in name:
        if session.path.isfile(name):
            pliki.append(name)
    return pliki


def listowanie_folderow_ftp(session):
    name = session.listdir(session.curdir)
    foldery = []
    for name in name:
        if session.path.isdir(name):
            foldery.append(name)
    return foldery


def generowanie_listy_do_usuniecia(lista_gd, lista_local):
    lista_do_usuniecia = []
    for y in range(len(lista_local)):
        jest_zsynchronizowane = False
        for x in range(len(lista_gd)):
            if lista_local[y] == lista_gd[x]:
                jest_zsynchronizowane = True
                break
        if jest_zsynchronizowane is False:
            lista_do_usuniecia.append(lista_local[y])

    return lista_do_usuniecia


def removeAccents(input_text):
    strange = 'ŮôῡΒძěἊἦëĐᾇόἶἧзвŅῑἼźἓŉἐÿἈΌἢὶЁϋυŕŽŎŃğûλВὦėἜŤŨîᾪĝžἙâᾣÚκὔჯᾏᾢĠфĞὝŲŊŁČῐЙῤŌὭŏყἀхῦЧĎὍОуνἱῺèᾒῘᾘὨШūლἚύсÁóĒἍŷöὄЗὤἥბĔõὅῥŋБщἝξĢюᾫაπჟῸდΓÕűřἅгἰშΨńģὌΥÒᾬÏἴქὀῖὣᾙῶŠὟὁἵÖἕΕῨčᾈķЭτἻůᾕἫжΩᾶŇᾁἣჩαἄἹΖеУŹἃἠᾞåᾄГΠКíōĪὮϊὂᾱიżŦИὙἮὖÛĮἳφᾖἋΎΰῩŚἷРῈĲἁéὃσňİΙῠΚĸὛΪᾝᾯψÄᾭêὠÀღЫĩĈμΆᾌἨÑἑïოĵÃŒŸζჭᾼőΣŻçųøΤΑËņĭῙŘАдὗპŰἤცᾓήἯΐÎეὊὼΘЖᾜὢĚἩħĂыῳὧďТΗἺĬὰὡὬὫÇЩᾧñῢĻᾅÆßшδòÂчῌᾃΉᾑΦÍīМƒÜἒĴἿťᾴĶÊΊȘῃΟúχΔὋŴćŔῴῆЦЮΝΛῪŢὯнῬũãáἽĕᾗნᾳἆᾥйᾡὒსᾎĆрĀüСὕÅýფᾺῲšŵкἎἇὑЛვёἂΏθĘэᾋΧĉᾐĤὐὴιăąäὺÈФĺῇἘſგŜæῼῄĊἏØÉПяწДĿᾮἭĜХῂᾦωთĦлðὩზკίᾂᾆἪпἸиᾠώᾀŪāоÙἉἾρаđἌΞļÔβĖÝᾔĨНŀęᾤÓцЕĽŞὈÞუтΈέıàᾍἛśìŶŬȚĳῧῊᾟάεŖᾨᾉςΡმᾊᾸįᾚὥηᾛġÐὓłγľмþᾹἲἔбċῗჰხοἬŗŐἡὲῷῚΫŭᾩὸùᾷĹēრЯĄὉὪῒᾲΜᾰÌœĥტ'

    ascii_replacements = 'UoyBdeAieDaoiiZVNiIzeneyAOiiEyyrZONgulVoeETUiOgzEaoUkyjAoGFGYUNLCiIrOOoqaKyCDOOUniOeiIIOSulEySAoEAyooZoibEoornBSEkGYOapzOdGOuraGisPngOYOOIikoioIoSYoiOeEYcAkEtIuiIZOaNaicaaIZEUZaiIaaGPKioIOioaizTIYIyUIifiAYyYSiREIaeosnIIyKkYIIOpAOeoAgYiCmAAINeiojAOYzcAoSZcuoTAEniIRADypUitiiIiIeOoTZIoEIhAYoodTIIIaoOOCSonyKaAsSdoACIaIiFIiMfUeJItaKEISiOuxDOWcRoiTYNLYTONRuaaIeinaaoIoysACRAuSyAypAoswKAayLvEaOtEEAXciHyiiaaayEFliEsgSaOiCAOEPYtDKOIGKiootHLdOzkiaaIPIIooaUaOUAIrAdAKlObEYiINleoOTEKSOTuTEeiaAEsiYUTiyIIaeROAsRmAAiIoiIgDylglMtAieBcihkoIrOieoIYuOouaKerYAOOiaMaIoht'

    translator = str.maketrans(strange, ascii_replacements)

    return input_text.translate(translator)


def email(nadawca, haslo_nadawcy, odbiorca, temat, kontent):
    mail_content = kontent
    receiver_address = 'arturlispl99@gmail.com'
    # Setup the MIME
    message = MIMEMultipart()
    message['From'] = nadawca
    message['To'] = odbiorca
    message['Subject'] = temat  # The subject line
    # The body and the attachments for the mail
    message.attach(MIMEText(mail_content, 'plain'))
    # Create SMTP session for sending the mail
    session = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
    session.starttls()  # enable security
    session.login(nadawca, haslo_nadawcy)  # login with mail_id and password
    text = message.as_string()
    session.sendmail(nadawca, odbiorca, text)
    session.quit()
    print('Mail Sent')


def usun_folder_local(sciezka):
    shutil.rmtree(sciezka, ignore_errors=False, onerror=None)


def usuwanie(id_folderu_nadrzednego_gd, ftpDir, session):
    print('Sprawdzam folder ' + ftpDir)
    bledy = []
    lista_nazw_plikow_gd = listing_nazw_plikow_gd_bez_powtorzen(id_folderu_nadrzednego_gd)

    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=1337)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token, protocol=0)
    service = build('drive', 'v3', credentials=creds)

    folder = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and '{id_folderu_nadrzednego_gd}' in parents",
        fields='files(id, name, parents, trashed)').execute()

    total = len(folder['files'])

    lista_nazw_plikow_gd_poprawiona = []
    lista_nazw_folderow_gd_poprawiona = []

    # usuwanie polskich znakow z nazw plikow i folderow
    for x in range(total):
        lista_nazw_folderow_gd_poprawiona.append(removeAccents(folder['files'][x]['name']))

    for x in range(len(lista_nazw_plikow_gd)):
        lista_nazw_plikow_gd_poprawiona.append(removeAccents(lista_nazw_plikow_gd[x]))

    session.chdir(ftpDir)

    lista_folderow_ftp = listowanie_folderow_ftp(session)
    lista_plikow_ftp = listowanie_plikow_ftp(session)

    lista_plikow_do_usuniecia = generowanie_listy_do_usuniecia(lista_nazw_plikow_gd_poprawiona, lista_plikow_ftp)
    lista_folderow_do_usuniecia = generowanie_listy_do_usuniecia(lista_nazw_folderow_gd_poprawiona, lista_folderow_ftp)

    for x in range(len(lista_plikow_do_usuniecia)):
        if session.path.exists(ftpDir + '/' + lista_plikow_do_usuniecia[x]):
            try:
                session.remove(lista_plikow_do_usuniecia[x])
            except:
                msg = 'Nie udalo sie usunac pliku ' + lista_plikow_do_usuniecia[x] + ' w folderze ' + ftpDir
                bledy.append(msg)

    for x in range(len(lista_folderow_do_usuniecia)):
        if session.path.exists(ftpDir + '/' + lista_folderow_do_usuniecia[x]):
            try:
                session.rmtree(lista_folderow_do_usuniecia[x])
            except:
                msg = 'Nie usunelo ' + ftpDir + '/' + lista_folderow_do_usuniecia[x] + ' w folderze ' + ftpDir
                bledy.append(msg)

    for x in range(total):
        if folder['files'][x]['trashed'] is False:
            if session.path.exists(ftpDir + '/' + removeAccents(folder['files'][x]['name'])):
                blad = usuwanie(folder['files'][x]['id'], ftpDir + '/' + removeAccents(folder['files'][x]['name']),
                                session)
                if len(blad) != 0:
                    bledy.extend(blad)

    return bledy


def pobieranie_i_wysylanie(lista_folderow_do_wyslania, host, user, passwd, nadawca,
                           haslo_nadawcy, odbiorca, ftpDir, session):
    bledy = []
    session.chdir(ftpDir)
    for x in range(len(lista_folderow_do_wyslania)):
        blad = download(lista_folderow_do_wyslania[x], 'Temp')

        if len(blad) != 0:
            bledy.extend(blad)

        localDir = os.curdir + '/Temp/' + lista_folderow_do_wyslania[x] + '/'
        nazwa_folderu_docelowa = removeAccents(lista_folderow_do_wyslania[x])
        ftpdir = ftpDir + '/' + nazwa_folderu_docelowa + '/'
        if not session.path.exists(ftpdir):
            session.mkdir(ftpDir + '/' + nazwa_folderu_docelowa)
        try:
            upload_dir(localDir, ftpdir, host, user, passwd)
        except FTPOSError as err:
            if err.errno == 550:
                msg = 'Skonczylo sie miejsce na serwerze FTP'
                email(nadawca, haslo_nadawcy, odbiorca, 'Blad synchronizacji serwera ftp', msg)
        except:
            blad = 'Wystapil blad podczas wysylania plikow z folderu ' + lista_folderow_do_wyslania[x]
            bledy.append(blad)
        if os.path.exists(os.curdir + '/Temp/' + lista_folderow_do_wyslania[x]):
            usun_folder_local(os.curdir + '/Temp/' + lista_folderow_do_wyslania[x])
    return bledy


def synchronizacja(ftpDir, id_folder_nadrzedny_gd, host, user, passwd, nadawca, haslo_nadawcy, odbiorca):
    try:
        os.mkdir('Temp')
    except:
        print('Folder tymczasowy istnieje')

    session = ftputil.FTPHost(host, user, passwd)
    session.chdir(ftpDir)
    bledy = []
    bledy_usuwania = []

    # usuwanie plikow z FTP
    if len(session.listdir(ftpDir)) != 0:
        bledy_usuwania = usuwanie(id_folder_nadrzedny_gd, ftpDir, session)

    if len(bledy_usuwania) != 0:
        bledy.extend(bledy_usuwania)

    session.chdir(ftpDir)

    lista_nazw_folderow_gd = listing_nazw_folderow_gd(id_folder_nadrzedny_gd)

    # pobranie i wysylanie brakujacych plikow i katalogow
    bledy_wysylania = pobieranie_i_wysylanie(lista_nazw_folderow_gd, host, user, passwd, nadawca, haslo_nadawcy,
                                             odbiorca, ftpDir, session)
    if len(bledy_wysylania) != 0:
        bledy.extend(bledy_wysylania)

    session.close()

    # mail z bledami
    msg = ''
    if len(bledy) != 0:
        for x in range(len(bledy)):
            msg = msg + '\n' + bledy[x]
        email(nadawca, haslo_nadawcy, odbiorca, 'Blad synchronizacji serwera FTP', msg)
