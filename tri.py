import argparse
import base64
import fcntl
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lingua import Language, LanguageDetectorBuilder

FOLDER = Path(__file__).resolve().parent
os.umask(0o077)

logger = logging.getLogger("wordpress-comments")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s | %(message)s")
for handler in (
    logging.StreamHandler(sys.stdout),
    RotatingFileHandler(
        FOLDER / "tri.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    ),
):
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def raw_content(comment):
    content = comment.get("content", {})
    return content.get("raw", content.get("rendered", ""))


def clean_text(content):
    parser = TextExtractor()
    parser.feed(content)
    text = " ".join(parser.parts)
    # Retirer les balises BBCode avant les URL :
    # [url=https://example.com]texte[/url] devient texte.
    text = re.sub(r"\[url=[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"\[/?url\]", " ", text, flags=re.I)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    return " ".join(text.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement le classement en indésirable",
    )
    args = parser.parse_args()

    with (FOLDER / "tri.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("Une autre exécution est déjà en cours.")
            return

        config = json.loads(
            (FOLDER / "config.json").read_text(encoding="utf-8")
        )
        api = config["api_url"].rstrip("/")
        if not api.startswith("https://"):
            raise ValueError("Une URL HTTPS est obligatoire.")

        minimum_score = float(config["minimum_score"])
        minimum_gap = float(config["minimum_gap"])
        minimum_letters = int(config["minimum_letters"])
        if not (
            0 <= minimum_score <= 1
            and 0 <= minimum_gap <= 1
            and minimum_letters >= 1
        ):
            raise ValueError("Seuils de configuration invalides.")

        token = base64.b64encode(
            (
                config["username"] + ":"
                + config["application_password"]
            ).encode("utf-8")
        ).decode("ascii")

        opener = urllib.request.build_opener(NoRedirect)

        def request(path="", params=None, payload=None):
            url = api + path
            if params:
                url += "?" + urllib.parse.urlencode(params)

            headers = {
                "Authorization": "Basic " + token,
                "Accept": "application/json",
                "User-Agent": "WordPress-Comment-Filter/1.0",
            }
            data = None
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
                headers["Content-Type"] = "application/json"

            req = urllib.request.Request(
                url, data=data, headers=headers
            )
            with opener.open(req, timeout=30) as response:
                return json.load(response), response.headers

        mode = "REEL" if args.apply else "SIMULATION"
        logger.info("Début du traitement | mode=%s", mode)

        # Lire toutes les pages avant toute modification.
        comments = {}
        page = 1
        while True:
            batch, headers = request(params={
                "context": "edit",
                "status": "hold",
                "type": "comment",
                "per_page": 100,
                "page": page,
                "orderby": "id",
                "order": "asc",
            })
            if not isinstance(batch, list):
                raise ValueError("Réponse WordPress inattendue.")

            for comment in batch:
                comments[comment["id"]] = comment

            total_pages = int(headers.get("X-WP-TotalPages", "1"))
            if not batch or page >= total_pages:
                break
            page += 1

        logger.info("Commentaires récupérés : %s", len(comments))
        detector = LanguageDetectorBuilder.from_all_languages().build()
        selected = 0
        changed = 0
        skipped = 0

        for comment_id, comment in comments.items():
            text = clean_text(raw_content(comment))
            if sum(char.isalpha() for char in text) < minimum_letters:
                logger.info("#%s | conservé | texte court", comment_id)
                continue

            scores = detector.compute_language_confidence_values(text)
            if len(scores) < 2:
                logger.info("#%s | conservé | langue incertaine", comment_id)
                continue

            best = scores[0]
            gap = best.value - scores[1].value
            french_score = next(
                (item.value for item in scores
                 if item.language == Language.FRENCH),
                0.0,
            )

            standard_candidate = (
                best.language != Language.FRENCH
                and best.value >= minimum_score
                and gap >= minimum_gap
            )

            english_candidate = (
                best.language == Language.ENGLISH
                and best.value >= 0.55
                and gap >= 0.30
                and french_score <= 0.01
            )

            candidate = standard_candidate or english_candidate

            if not candidate:
                alternatives = ", ".join(
                    f"{item.language.name}={item.value:.3f}"
                    for item in scores[:3]
                )
                french_score = next(
                    (item.value for item in scores
                     if item.language == Language.FRENCH),
                    0.0,
                )
                logger.info(
                    "#%s | diagnostic : %s | français=%.3f | écart=%.3f",
                    comment_id, alternatives, french_score, gap,
                )
                logger.info(
                    "#%s | conservé | langue=%s | score=%.3f",
                    comment_id, best.language.name, best.value,
                )
                continue

            selected += 1
            if not args.apply:
                logger.info(
                    "#%s | serait indésirable | langue=%s | score=%.3f",
                    comment_id, best.language.name, best.value,
                )
                continue

            # Relire le commentaire juste avant de le modifier.
            current, _ = request(
                f"/{comment_id}", params={"context": "edit"}
            )
            if (
                current.get("status") != "hold"
                or raw_content(current) != raw_content(comment)
            ):
                skipped += 1
                logger.info(
                    "#%s | ignoré : statut ou texte modifié entre-temps",
                    comment_id,
                )
                continue

            logger.info("#%s | demande de classement", comment_id)
            updated, _ = request(
                f"/{comment_id}", payload={"status": "spam"}
            )
            if updated.get("status") != "spam":
                raise ValueError(
                    f"Classement non confirmé pour #{comment_id}"
                )

            changed += 1
            logger.info(
                "#%s | CLASSE INDESIRABLE | langue=%s | score=%.3f",
                comment_id, best.language.name, best.value,
            )

        logger.info(
            "BILAN | mode=%s | analysés=%s | sélectionnés=%s"
            " | classés=%s | ignorés après relecture=%s",
            mode, len(comments), selected, changed, skipped,
        )


try:
    main()
except urllib.error.HTTPError as error:
    logger.error(
        "Arrêt : HTTP %s. Consulter les actions déjà confirmées"
        " dans le journal avant de relancer.",
        error.code,
    )
    sys.exit(1)
except Exception as error:
    logger.error(
        "Arrêt : %s. Vérifier la configuration et la connexion."
        " Des actions précédentes peuvent déjà avoir été appliquées.",
        type(error).__name__,
    )
    sys.exit(1)