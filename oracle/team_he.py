"""Hebrew (Winner) team names -> canonical names used in data/matches.csv.
Unknown names are logged to data/winner_unmapped.txt and self-learned when a fixture pairing is unambiguous
(learned pairs live in data/team_he_learned.json)."""
import json
from .config import DATA

SEED = {
    # --- Israel
    'בית"ר ירושלים': "Beitar Jerusalem", "בני סכנין": "Bnei Sakhnin", "הפועל באר שבע": "Hapoel Be'er Sheva",
    "הפועל חיפה": "Hapoel Haifa", "הפועל ירושלים": "Hapoel Jerusalem", "הפועל פתח תקוה": "Hapoel Petah Tikva",
    "הפועל רמת גן": "Hapoel Ramat Gan", "הפועל תל אביב": "Hapoel Tel-Aviv", "מכבי חיפה": "Maccabi Haifa",
    "מכבי נתניה": "Maccabi Netanya", "מכבי פתח תקוה": "Maccabi Petah Tikva", "מכבי תל אביב": "Maccabi Tel Aviv",
    "עירוני טבריה": "Ironi Tiberias", "עירוני קרית שמונה": "Hapoel Kiryat Shmona", "הפועל חדרה": "Hapoel Hadera Eran",
    "מ.ס. אשדוד": "Ashdod", "אשדוד": "Ashdod", "מכבי בני ריינה": "Maccabi Raina", "בני ריינה": "Maccabi Raina",
    # --- Europa / Champions League (clubs from outside the big 4)
    "אולימפיאקוס": "Olympiakos", "אומוניה ניקוסיה": "Omonia Nicosia", "אופי כרתים": "OFI Crete", "אלקמאר": "AZ Alkmaar",
    "אנדרלכט": "Anderlecht", "אררט ארמניה": "Ararat-Armenia", "באייר לברקוזן": "Leverkusen", "ביאליסטוק": "Jagiellonia Bialystok",
    "בנפיקה ליסבון": "Benfica", "בשיקטאש": "Beşiktaş", "דינמו זגרב": "Dinamo Zagreb", "הופנהיים": "TSG Hoffenheim",
    "ויקטוריה פלזן": "Viktoria Plzeň", "זלצבורג": "RB Salzburg", "טורנסה": "Torreense", "לבסקי סופיה": "Levski Sofia",
    "לילסטרום": "Lillestrom", "לך פוזנן": "Lech Poznan", "ניימיכן": "NEC Nijmegen", "סלטיק": "Celtic",
    "סן ז'ילואז": "Union St.-Gilloise", "ספרטה פראג": "Sparta Praha", "פרנצוורוש": "Ferencvaros", "צלייה": "NK Celje",
    "שטורם גראץ": "SK Sturm Graz", "באיירן מינכן": "Bayern", "בורוסיה דורטמונד": "Dortmund", "פנרבחצ'ה": "Fenerbahce",
    "פיינורד": "Feyenoord", "גלאטסראיי": "Galatasaray", "גלטסראיי": "Galatasaray", "בודו גלימט": "Bodo/Glimt",
    "בודה גלימט": "Bodo/Glimt", "קלאב ברוז'": "Club Brugge", "לאסק לינץ": "LASK Linz", "פ.ס.וו איינדהובן": "PSV",
    "איינדהובן": "PSV", "ר.ב. לייפציג": "RB Leipzig", "לייפציג": "RB Leipzig", "סבאח": "Sabah FK", "שחטאר דונייצק": "Shakhtar",
    "סלביה פראג": "Slavia Praha", "ספורטינג ליסבון": "Sporting", "שטוטגרט": "VfB Stuttgart", "ויקינג": "Viking FK",
    "סלובן ברטיסלבה": "ŠK Slovan Bratislava", "פורטו": "Porto", "אי.אי.קי אתונה": "AEK Athens", "א.א.ק אתונה": "AEK Athens",
    "אי אי קיי אתונה": "AEK Athens", "קלאב ברוג": "Club Brugge",
    # --- England
    "אברטון": "Everton", "איפסוויץ'": "Ipswich", "אסטון וילה": "Aston Villa", "ארסנל": "Arsenal", "בורנמות'": "Bournemouth",
    "ברייטון": "Brighton", "ברנטפורד": "Brentford", "האל": "Hull", "טוטנהאם": "Tottenham", "ליברפול": "Liverpool",
    "לידס": "Leeds", "מנצ'סטר יונייטד": "Man United", "מנצ'סטר סיטי": "Man City", "נוטינגהאם פורסט": "Nott'm Forest",
    "ניוקאסל": "Newcastle", "סנדרלנד": "Sunderland", "פולהאם": "Fulham", "צ'לסי": "Chelsea", "קובנטרי": "Coventry",
    "קריסטל פאלאס": "Crystal Palace", "ווסטהאם": "West Ham", "וולבס": "Wolves", "וולברהמפטון": "Wolves",
    # --- Spain
    "אוסאסונה": "Osasuna", "אלאבס": "Alaves", "אלצ'ה": "Elche", "אספניול": "Espanol", "אתלטיק בילבאו": "Ath Bilbao",
    "אתלטיקו מדריד": "Ath Madrid", "ברצלונה": "Barcelona", "דפורטיבו לה קורוניה": "Deportivo", "ויאריאל": "Villarreal",
    "ולנסיה": "Valencia", "חטאפה": "Getafe", "לבאנטה": "Levante", "מלאגה": "Malaga", "סביליה": "Sevilla",
    "סלטה ויגו": "Celta", "ראיו וייקאנו": "Vallecano", "ראסינג דה סנטנדר": "Santander", "ריאל בטיס": "Betis",
    "ריאל מדריד": "Real Madrid", "ריאל סוסיאדד": "Sociedad", "ג'ירונה": "Girona", "מיורקה": "Mallorca", "ריאל אוביידו": "Oviedo",
    # --- Italy
    "אודינזה": "Udinese", "אטאלנטה": "Atalanta", "אינטר": "Inter", "בולוניה": "Bologna", "גנואה": "Genoa",
    "ונציה": "Venezia", "טורינו": "Torino", "לאציו": "Lazio", "לצ'ה": "Lecce", "מונזה": "Monza", "נאפולי": "Napoli",
    "ססואולו": "Sassuolo", "פארמה": "Parma", "פיורנטינה": "Fiorentina", "פרוסינונה": "Frosinone", "קומו": "Como",
    "קליארי": "Cagliari", "רומא": "Roma", "יובנטוס": "Juventus", "מילאן": "Milan", "ורונה": "Verona", "פיזה": "Pisa",
    # --- France
    "אוקזר": "Auxerre", "אנז'ר": "Angers", "ברסט": "Brest", "טולוז": "Toulouse", "טרואה": "Troyes", "לאנס": "Lens",
    "לה האבר": "Le Havre", "לה מאן": "Le Mans", "לוריין": "Lorient", "ליל": "Lille", "מונאקו": "Monaco", "ניס": "Nice",
    "פ.צ. פאריס": "Paris FC", "פאריס סן ז'רמן": "Paris SG", "שטראסבורג": "Strasbourg", "ליון": "Lyon", "מארסיי": "Marseille",
    "ראן": "Rennes", "נאנט": "Nantes", "מץ": "Metz",
}
LEARNED_JSON = DATA / "team_he_learned.json"
UNMAPPED_TXT = DATA / "winner_unmapped.txt"


def clean(s):
    return (s or "").replace("‪", "").replace("‫", "").replace("‬", "").replace("‮", "").strip()


def load():
    d = dict(SEED)
    if LEARNED_JSON.exists():
        try:
            d.update(json.loads(LEARNED_JSON.read_text(encoding="utf-8")))
        except Exception:
            pass
    return d


def save_learned(new):
    cur = {}
    if LEARNED_JSON.exists():
        try:
            cur = json.loads(LEARNED_JSON.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    cur.update(new)
    LEARNED_JSON.write_text(json.dumps(cur, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
