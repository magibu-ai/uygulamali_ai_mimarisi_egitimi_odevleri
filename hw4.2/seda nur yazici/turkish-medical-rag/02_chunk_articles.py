from pathlib import Path
import re

import pandas as pd
from transformers import AutoTokenizer


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path("data/articles_500.parquet")
OUTPUT_FILE = Path("data/chunks_parent_child.parquet")

TOKENIZER_MODEL = "BAAI/bge-m3"


# ============================================================
# PARENT AYARLARI
# ============================================================

PARENT_MAX_TOKENS = 1200

# Sert minimum değildir.
# Son parent küçükse mümkünse yeniden dengelenir.
MIN_PARENT_TOKENS = 200


# ============================================================
# CHILD AYARLARI
# ============================================================

CHILD_MAX_TOKENS = 320

# Sert minimum değildir.
# Son child küçükse mümkünse yeniden dengelenir.
MIN_CHILD_TOKENS = 80

CHILD_OVERLAP_UNITS = 1


# ============================================================
# SEMANTIC UNIT AYARLARI
# ============================================================

SHORT_HEADING_MAX_TOKENS = 40


# ============================================================
# DUPLICATE TEMİZLİĞİ
# ============================================================

MAX_DUPLICATE_PHRASE_WORDS = 12
MAX_BOUNDARY_DUPLICATE_WORDS = 12


# ============================================================
# NAVIGATION TEMİZLİĞİ
# ============================================================

# Navigation bloğu için minimum item sayısı.
NAV_MIN_ITEMS = 5

# En az kaç soru olmalı?
NAV_MIN_QUESTIONS = 4

# Makalenin yalnızca başlangıç bölgesinde navigation aranır.
NAV_SCAN_START_MAX_TOKENS = 650

# Güvenlik için başlangıçta maksimum kaç segment taransın?
NAV_SCAN_MAX_SEGMENTS = 80

# Tek bir navigation/menu segmentinin maksimum uzunluğu.
NAV_ITEM_MAX_TOKENS = 100


# ============================================================
# TEMİZLİK İSTATİSTİKLERİ
# ============================================================

CLEANING_STATS = {
    "duplicate_phrases_removed": 0,
    "duplicate_segments_removed": 0,

    "boundary_duplicate_phrases_removed": 0,
    "boundary_duplicate_words_removed": 0,

    "navigation_blocks_removed": 0,
    "navigation_items_removed": 0,
    "navigation_questions_removed": 0,
    "articles_with_navigation_removed": 0,
}


# ============================================================
# TOKENIZER
# ============================================================

print("BGE-M3 tokenizer yükleniyor...")

tokenizer = AutoTokenizer.from_pretrained(
    TOKENIZER_MODEL
)

print("Tokenizer yüklendi.")


# ============================================================
# TEMEL METİN FONKSİYONLARI
# ============================================================

def clean_text(text):
    """
    Temel whitespace temizliği.

    Satır yapıları tamamen yok edilmez çünkü
    heading/paragraf bilgisi chunking için faydalıdır.
    """

    if text is None:
        return ""

    try:
        if pd.isna(text):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Aynı satırdaki fazla boşlukları temizle.
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # Çok fazla boş satırı azalt.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


def count_tokens(text):
    """
    BGE-M3 tokenizer'a göre token sayısı.
    """

    if not text:
        return 0

    return len(
        tokenizer.encode(
            text,
            add_special_tokens=False
        )
    )


def join_units(units):
    """
    Semantic unit listesini tek metne dönüştürür.
    """

    return " ".join(
        unit.strip()
        for unit in units
        if unit and unit.strip()
    ).strip()


def units_token_count(units):
    """
    Semantic unit grubunun gerçek token sayısı.
    """

    return count_tokens(
        join_units(units)
    )


# ============================================================
# TOKEN FALLBACK
# ============================================================

def split_by_tokens(text, max_tokens):
    """
    Tek bir semantic unit bile maksimum sınırı geçerse
    son çare olarak tokenizer seviyesinde böler.
    """

    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False
    )

    pieces = []

    for start in range(
        0,
        len(token_ids),
        max_tokens
    ):

        piece_ids = token_ids[
            start:start + max_tokens
        ]

        piece = tokenizer.decode(
            piece_ids,
            skip_special_tokens=True
        ).strip()

        if piece:
            pieces.append(piece)

    return pieces


# ============================================================
# DUPLICATE NORMALIZATION
# ============================================================

def normalize_for_duplicate_check(text):
    """
    Segment / phrase karşılaştırması için normalize eder.
    """

    text = str(text).strip().casefold()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def normalize_word_for_duplicate_check(word):
    """
    Tek kelimeyi duplicate karşılaştırması için normalize eder.
    """

    word = str(word).strip().casefold()

    word = re.sub(
        r"^[^\wçğıöşü]+|[^\wçğıöşü]+$",
        "",
        word,
        flags=re.IGNORECASE
    )

    return word


def normalized_word_sequence(words):
    """
    Kelime listesini normalize edilmiş listeye çevirir.
    """

    return [
        normalize_word_for_duplicate_check(word)
        for word in words
    ]


def is_title_like_word(word):
    """
    Tek kelimelik tekrarın heading kaynaklı olma
    olasılığını kontrol eder.

    Örnek:
        Öksürük Öksürük

    temizlenebilir.

    Ancak:
        çok çok

    gibi doğal lowercase tekrarları korunur.
    """

    word = str(word).strip()

    word = re.sub(
        r"^[^\wÇĞİÖŞÜçğıöşü]+",
        "",
        word
    )

    if not word:
        return False

    return word[0].isupper()


# ============================================================
# SEGMENT İÇİNDE DUPLICATE PHRASE TEMİZLİĞİ
# ============================================================

def remove_adjacent_duplicate_phrases(
    text,
    max_phrase_words=MAX_DUPLICATE_PHRASE_WORDS
):
    """
    Aynı segment içinde art arda tekrar eden ifadeleri
    temizler.

    Örnek:

        Böbrek Yetmezliği Böbrek Yetmezliği Böbrekler...
        ->
        Böbrek Yetmezliği Böbrekler...


        Rahim ağzı kanserinden korunmak için;
        Rahim ağzı kanserinden korunmak için;
        ->
        Rahim ağzı kanserinden korunmak için;


        Öksürük Öksürük En sık...
        ->
        Öksürük En sık...
    """

    text = str(text).strip()

    if not text:
        return text

    words = text.split()

    if len(words) < 2:
        return text

    changed = True
    safety_round = 0

    MAX_ROUNDS = 200

    while (
        changed
        and safety_round < MAX_ROUNDS
    ):

        changed = False
        safety_round += 1

        # ----------------------------------------------------
        # 2+ kelimelik phrase duplicate
        # ----------------------------------------------------

        duplicate_found = False

        for start in range(len(words)):

            remaining = (
                len(words) - start
            )

            max_n = min(
                max_phrase_words,
                remaining // 2
            )

            # Uzun phrase önce kontrol edilir.
            for phrase_len in range(
                max_n,
                1,
                -1
            ):

                first_phrase = words[
                    start:
                    start + phrase_len
                ]

                second_phrase = words[
                    start + phrase_len:
                    start + (2 * phrase_len)
                ]

                first_norm = (
                    normalized_word_sequence(
                        first_phrase
                    )
                )

                second_norm = (
                    normalized_word_sequence(
                        second_phrase
                    )
                )

                if (
                    not all(first_norm)
                    or not all(second_norm)
                ):
                    continue

                if first_norm != second_norm:
                    continue

                # İkinci kopyayı kaldır.
                del words[
                    start + phrase_len:
                    start + (2 * phrase_len)
                ]

                CLEANING_STATS[
                    "duplicate_phrases_removed"
                ] += 1

                changed = True
                duplicate_found = True

                break

            if duplicate_found:
                break

        if changed:
            continue

        # ----------------------------------------------------
        # Tek kelimelik heading duplicate
        # ----------------------------------------------------

        i = 0

        while i < len(words) - 1:

            first_norm = (
                normalize_word_for_duplicate_check(
                    words[i]
                )
            )

            second_norm = (
                normalize_word_for_duplicate_check(
                    words[i + 1]
                )
            )

            if (
                first_norm
                and first_norm == second_norm
                and len(first_norm) >= 4
                and is_title_like_word(
                    words[i]
                )
            ):

                del words[
                    i + 1
                ]

                CLEANING_STATS[
                    "duplicate_phrases_removed"
                ] += 1

                changed = True

                continue

            i += 1

    return " ".join(
        words
    ).strip()


# ============================================================
# METNİ SEGMENTLERE AYIR
# ============================================================

def split_into_segments(text):
    """
    Metni önce satır/paragraf, daha sonra cümle sınırlarına
    göre ayırır.
    """

    text = clean_text(text)

    if not text:
        return []

    segments = []

    blocks = re.split(
        r"\n+",
        text
    )

    for block in blocks:

        block = block.strip()

        if not block:
            continue

        sentences = re.split(
            r"(?<=[.!?])\s+",
            block
        )

        for sentence in sentences:

            sentence = (
                sentence.strip()
            )

            if not sentence:
                continue

            sentence = (
                remove_adjacent_duplicate_phrases(
                    sentence
                )
            )

            if sentence:
                segments.append(
                    sentence
                )

    return segments


# ============================================================
# ARDIŞIK AYNI SEGMENTLERİ TEMİZLE
# ============================================================

def remove_consecutive_duplicate_segments(
    segments
):
    """
    Art arda birebir aynı segmentleri kaldırır.
    """

    cleaned = []

    for segment in segments:

        segment = (
            segment.strip()
        )

        if not segment:
            continue

        if cleaned:

            current_norm = (
                normalize_for_duplicate_check(
                    segment
                )
            )

            previous_norm = (
                normalize_for_duplicate_check(
                    cleaned[-1]
                )
            )

            if (
                current_norm
                == previous_norm
            ):

                CLEANING_STATS[
                    "duplicate_segments_removed"
                ] += 1

                continue

        cleaned.append(
            segment
        )

    return cleaned


# ============================================================
# NAVIGATION YARDIMCI FONKSİYONLARI
# ============================================================

BULLET_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    r"[-–—•*]\s*"
    r"|"
    r"\d+\s*[\.\)-]\s*"
    r")"
)


INLINE_BULLET_PATTERN = re.compile(
    r"\s[-–—•*]\s+"
)


def starts_with_list_marker(text):
    """
    Segment bullet/number ile başlıyor mu?
    """

    return bool(
        BULLET_PREFIX_PATTERN.match(
            str(text)
        )
    )


def count_navigation_item_markers(text):
    """
    Segment içindeki olası menu/list item sayısını tahmin eder.
    """

    text = str(text)

    count = 0

    if starts_with_list_marker(
        text
    ):
        count += 1

    count += len(
        INLINE_BULLET_PATTERN.findall(
            text
        )
    )

    return count


def looks_like_navigation_segment(text):
    """
    Segment navigation/menu item benzeri mi?

    Saf soru olması şart değil.

    Örnek:

        - Boyun Fıtığı Nedir?

        - Boyun Fıtığı Egzersizleri
          - Boyun Fıtığı Nasıl Teşhis Edilir?

    ikisi de menu parçası olabilir.
    """

    text = str(text).strip()

    if not text:
        return False

    marker_count = (
        count_navigation_item_markers(
            text
        )
    )

    question_count = (
        text.count("?")
    )

    token_count = (
        count_tokens(text)
    )

    if (
        marker_count == 0
    ):
        return False

    # Çok uzun, gerçek açıklama içeren segmentleri
    # navigation kabul etmeyelim.
    if (
        token_count
        > NAV_ITEM_MAX_TOKENS
        and question_count <= 1
        and marker_count <= 1
    ):
        return False

    return True


def contains_navigation_phrase(text):
    """
    TOC/navigation olduğuna dair güçlü ipuçları.
    """

    normalized = (
        normalize_for_duplicate_check(
            text
        )
    )

    phrases = [
        "sık sorulan sorular",
        "sıkça sorulan sorular",
        "hakkında sık sorulan sorular",
        "ile ilgili sık sorulan sorular",
        "merak edilen sorular",
    ]

    return any(
        phrase in normalized
        for phrase in phrases
    )


def looks_like_real_questionnaire_context(text):
    """
    Gerçek tıbbi checklist / doktor soru listesi
    navigation sanılmasın.

    Örnek:
        Doktor aşağıdaki soruları sorabilir...
    """

    normalized = (
        normalize_for_duplicate_check(
            text
        )
    )

    phrases = [
        "aşağıdaki soruları",
        "şu soruları",
        "soruları sorabilir",
        "doktor",
        "riskinizi değerlendirmek",
        "risk değerlendirmesi",
        "kendinize",
        "evet yanıtı",
        "evet cevabı",
        "testi uygulayın",
        "kontrol listesi",
    ]

    return any(
        phrase in normalized
        for phrase in phrases
    )


def normalize_question_for_search(text):
    """
    Navigation listesindeki soruyu sonraki gerçek bölümle
    karşılaştırmak için normalize eder.
    """

    text = str(text)

    text = re.sub(
        r"^\s*(?:[-–—•*]|\d+\s*[\.\)-])\s*",
        "",
        text
    )

    text = (
        normalize_for_duplicate_check(
            text
        )
    )

    text = re.sub(
        r"[^\wçğıöşü\s]",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def block_question_repeated_after(
    segments,
    block_start,
    block_end
):
    """
    Navigation bloğundaki ilk sorulardan biri,
    listenin hemen ardından gerçek bölüm başlığı olarak
    tekrar ediyor mu?

    Bu güçlü bir TOC/navigation sinyalidir.
    """

    candidate_questions = []

    for segment in segments[
        block_start:block_end
    ]:

        if "?" not in segment:
            continue

        parts = segment.split("?")

        for part in parts[:-1]:

            question = (
                normalize_question_for_search(
                    part
                )
            )

            if (
                len(question.split()) >= 3
            ):
                candidate_questions.append(
                    question
                )

    if not candidate_questions:
        return False

    after_text = " ".join(
        segments[
            block_end:
            min(
                len(segments),
                block_end + 5
            )
        ]
    )

    after_normalized = (
        normalize_question_for_search(
            after_text
        )
    )

    for question in candidate_questions[:5]:

        if (
            len(question) >= 15
            and question in after_normalized
        ):
            return True

    return False


# ============================================================
# BAŞLANGIÇ NAVIGATION BLOĞUNU TEMİZLE
# ============================================================

def remove_initial_navigation_block(
    segments
):
    """
    Makalenin başında bulunan TOC/menu tarzı listeleri kaldırır.

    Artık yalnızca:

        5 ardışık soru

    aramıyoruz.

    Bunun yerine:

        - en az 5 menu/list item
        - en az 4 soru
        - güçlü navigation sinyali

    aranır.

    Güçlü sinyal:
        * 7+ menu item olması
        * "Sık Sorulan Sorular" ifadesi
        * listedeki sorunun hemen sonra gerçek bölüm olarak
          tekrar etmesi

    Gerçek doktor/checklist soru listelerine mümkün olduğunca
    dokunulmaz.
    """

    if not segments:
        return segments

    cumulative_tokens = 0
    index = 0

    while (
        index < len(segments)
        and index < NAV_SCAN_MAX_SEGMENTS
    ):

        if (
            cumulative_tokens
            > NAV_SCAN_START_MAX_TOKENS
        ):
            break

        current = segments[
            index
        ]

        if not looks_like_navigation_segment(
            current
        ):

            cumulative_tokens += (
                count_tokens(
                    current
                )
            )

            index += 1

            continue

        block_start = index
        block_end = index

        item_count = 0
        question_count = 0

        # ----------------------------------------------------
        # Ardışık menu/list segmentlerini tara
        # ----------------------------------------------------

        while (
            block_end < len(segments)
            and looks_like_navigation_segment(
                segments[
                    block_end
                ]
            )
        ):

            segment = segments[
                block_end
            ]

            marker_count = max(
                1,
                count_navigation_item_markers(
                    segment
                )
            )

            item_count += (
                marker_count
            )

            question_count += (
                segment.count("?")
            )

            block_end += 1

        block_text = " ".join(
            segments[
                block_start:block_end
            ]
        )

        previous_context = " ".join(
            segments[
                max(0, block_start - 2):
                block_start
            ]
        )

        has_nav_phrase = (
            contains_navigation_phrase(
                block_text
            )
        )

        repeated_after = (
            block_question_repeated_after(
                segments,
                block_start,
                block_end
            )
        )

        probable_questionnaire = (
            looks_like_real_questionnaire_context(
                previous_context
            )
        )

        enough_items = (
            item_count
            >= NAV_MIN_ITEMS
        )

        enough_questions = (
            question_count
            >= NAV_MIN_QUESTIONS
        )

        strong_navigation_signal = (
            has_nav_phrase
            or item_count >= 7
            or repeated_after
        )

        should_remove = (
            enough_items
            and enough_questions
            and strong_navigation_signal
        )

        # Eğer güçlü bir "Sık Sorulan Sorular" sinyali yoksa
        # gerçek doktor/checklist listesini koru.
        if (
            should_remove
            and probable_questionnaire
            and not has_nav_phrase
            and not repeated_after
        ):
            should_remove = False

        if should_remove:

            CLEANING_STATS[
                "navigation_blocks_removed"
            ] += 1

            CLEANING_STATS[
                "navigation_items_removed"
            ] += item_count

            CLEANING_STATS[
                "navigation_questions_removed"
            ] += question_count

            CLEANING_STATS[
                "articles_with_navigation_removed"
            ] += 1

            cleaned = (
                segments[:block_start]
                + segments[block_end:]
            )

            return cleaned

        # Bulunan run navigation değilse devam et.
        for segment in segments[
            block_start:block_end
        ]:

            cumulative_tokens += (
                count_tokens(
                    segment
                )
            )

        index = block_end

    return segments


# ============================================================
# KISA HEADING / SORU TESPİTİ
# ============================================================

def looks_like_short_heading_or_question(
    text
):
    """
    Kısa heading veya soru segmentlerini tespit eder.
    """

    text = str(text).strip()

    if not text:
        return False

    token_count = (
        count_tokens(
            text
        )
    )

    if (
        token_count
        > SHORT_HEADING_MAX_TOKENS
    ):
        return False

    if text.endswith("?"):
        return True

    has_terminal_punctuation = bool(
        re.search(
            r"[.!?…]$",
            text
        )
    )

    if not has_terminal_punctuation:
        return True

    return False


# ============================================================
# SEMANTIC UNIT BOUNDARY DUPLICATE TEMİZLİĞİ
# ============================================================

def find_boundary_overlap_word_count(
    previous_unit,
    current_unit
):
    """
    Önceki semantic unit'ın sonu ile yeni semantic unit'ın
    başında aynı phrase var mı?

    Örnek:

        previous:
            "... belirtiler arasında Folik asit eksikliği"

        current:
            "Folik asit eksikliği Hamilelik döneminde..."

    overlap = 3 word
    """

    prev_words = (
        str(previous_unit)
        .split()
    )

    curr_words = (
        str(current_unit)
        .split()
    )

    if (
        not prev_words
        or not curr_words
    ):
        return 0

    max_n = min(
        MAX_BOUNDARY_DUPLICATE_WORDS,
        len(prev_words),
        len(curr_words)
    )

    for n in range(
        max_n,
        0,
        -1
    ):

        prev_suffix = (
            prev_words[-n:]
        )

        curr_prefix = (
            curr_words[:n]
        )

        prev_norm = (
            normalized_word_sequence(
                prev_suffix
            )
        )

        curr_norm = (
            normalized_word_sequence(
                curr_prefix
            )
        )

        if (
            not all(prev_norm)
            or not all(curr_norm)
        ):
            continue

        if (
            prev_norm
            != curr_norm
        ):
            continue

        # ----------------------------------------------------
        # Tek kelimelik overlap için temkinli davran.
        # ----------------------------------------------------

        if n == 1:

            word = prev_suffix[0]

            normalized = prev_norm[0]

            if (
                len(normalized) < 4
                or not is_title_like_word(
                    word
                )
            ):
                continue

        return n

    return 0


def remove_semantic_unit_boundary_duplicates(
    units
):
    """
    Komşu semantic unit sınırındaki tekrarları kaldırır.

    Örnek:

        Unit A:
            ... Öksürük

        Unit B:
            Öksürük En sık görülen...

    ->

        Unit A:
            ... Öksürük

        Unit B:
            En sık görülen...


    Örnek:

        Unit A:
            ... Çoklu (çoğul) gebelik

        Unit B:
            Çoklu (çoğul) gebelik
            Tüp bebek tedavisiyle...

    ->

        Unit B:
            Tüp bebek tedavisiyle...
    """

    if not units:
        return []

    cleaned = []

    for unit in units:

        current = (
            str(unit)
            .strip()
        )

        if not current:
            continue

        if not cleaned:

            cleaned.append(
                current
            )

            continue

        # Aynı boundary'de birden fazla tekrar varsa
        # tekrar tekrar temizle.
        while (
            cleaned
            and current
        ):

            previous = (
                cleaned[-1]
            )

            overlap_words = (
                find_boundary_overlap_word_count(
                    previous,
                    current
                )
            )

            if overlap_words == 0:
                break

            current_words = (
                current.split()
            )

            current = " ".join(
                current_words[
                    overlap_words:
                ]
            ).strip()

            CLEANING_STATS[
                "boundary_duplicate_phrases_removed"
            ] += 1

            CLEANING_STATS[
                "boundary_duplicate_words_removed"
            ] += overlap_words

        if not current:
            continue

        # Boundary temizliğinden sonra segment içinde tekrar
        # oluşmuşsa bir kez daha normalize et.
        current = (
            remove_adjacent_duplicate_phrases(
                current
            )
        )

        if current:
            cleaned.append(
                current
            )

    return cleaned


# ============================================================
# SEMANTIC UNIT OLUŞTURMA
# ============================================================

def create_semantic_units(text):
    """
    Makale -> semantic unit pipeline.

    Sıra:

        1. Segmentasyon
        2. Segment içi duplicate temizliği
        3. Ardışık duplicate segment temizliği
        4. Başlangıç navigation/menu temizliği
        5. Kısa heading/question + açıklama grouping
        6. Semantic-unit boundary duplicate temizliği
        7. Son duplicate kontrolü
    """

    segments = (
        split_into_segments(
            text
        )
    )

    segments = (
        remove_consecutive_duplicate_segments(
            segments
        )
    )

    segments = (
        remove_initial_navigation_block(
            segments
        )
    )

    units = []

    i = 0

    while i < len(segments):

        current = (
            segments[i]
            .strip()
        )

        if not current:

            i += 1
            continue

        # ----------------------------------------------------
        # Kısa heading / soru + sonraki açıklama
        # ----------------------------------------------------

        if (
            looks_like_short_heading_or_question(
                current
            )
            and i + 1 < len(segments)
        ):

            next_segment = (
                segments[
                    i + 1
                ].strip()
            )

            combined = (
                current
                + " "
                + next_segment
            )

            combined = (
                remove_adjacent_duplicate_phrases(
                    combined
                )
            )

            if (
                count_tokens(
                    combined
                )
                <= CHILD_MAX_TOKENS
            ):

                units.append(
                    combined
                )

                i += 2
                continue

        # ----------------------------------------------------
        # Normal segment
        # ----------------------------------------------------

        current = (
            remove_adjacent_duplicate_phrases(
                current
            )
        )

        current_tokens = (
            count_tokens(
                current
            )
        )

        if (
            current_tokens
            <= CHILD_MAX_TOKENS
        ):

            units.append(
                current
            )

        else:

            pieces = (
                split_by_tokens(
                    current,
                    CHILD_MAX_TOKENS
                )
            )

            units.extend(
                pieces
            )

        i += 1

    # --------------------------------------------------------
    # FINAL SEMANTIC UNIT BOUNDARY CLEANING
    # --------------------------------------------------------

    units = (
        remove_semantic_unit_boundary_duplicates(
            units
        )
    )

    # --------------------------------------------------------
    # Son consecutive duplicate kontrolü
    # --------------------------------------------------------

    units = (
        remove_consecutive_duplicate_segments(
            units
        )
    )

    return units


# ============================================================
# PARENT GREEDY PACKING
# ============================================================

def pack_units_no_overlap(
    units,
    max_tokens
):
    """
    Semantic unit'ları parent'lara greedy şekilde paketler.
    """

    chunks = []
    current = []

    for unit in units:

        if not current:

            current = [
                unit
            ]

            continue

        candidate = (
            current
            + [unit]
        )

        if (
            units_token_count(
                candidate
            )
            <= max_tokens
        ):

            current.append(
                unit
            )

        else:

            chunks.append(
                current
            )

            current = [
                unit
            ]

    if current:
        chunks.append(
            current
        )

    return chunks


# ============================================================
# PARENT TAIL REBALANCING
# ============================================================

def rebalance_parent_tail(
    chunks,
    min_tokens,
    max_tokens
):
    """
    Son parent çok küçükse önceki parent ile dengeler.
    """

    if len(chunks) < 2:
        return chunks

    chunks = [
        chunk.copy()
        for chunk in chunks
    ]

    while (
        len(chunks) >= 2
        and units_token_count(
            chunks[-1]
        ) < min_tokens
    ):

        previous = (
            chunks[-2]
        )

        last = (
            chunks[-1]
        )

        # ----------------------------------------------------
        # İkisi tek parent'a sığıyor mu?
        # ----------------------------------------------------

        merged = (
            previous
            + last
        )

        if (
            units_token_count(
                merged
            )
            <= max_tokens
        ):

            chunks[-2] = (
                merged
            )

            chunks.pop()

            continue

        # ----------------------------------------------------
        # Previous'tan semantic unit taşı
        # ----------------------------------------------------

        if len(previous) <= 1:
            break

        moved_unit = (
            previous[-1]
        )

        candidate_previous = (
            previous[:-1]
        )

        candidate_last = (
            [moved_unit]
            + last
        )

        previous_tokens = (
            units_token_count(
                candidate_previous
            )
        )

        last_tokens = (
            units_token_count(
                candidate_last
            )
        )

        if (
            previous_tokens
            < min_tokens
        ):
            break

        if (
            last_tokens
            > max_tokens
        ):
            break

        chunks[-2] = (
            candidate_previous
        )

        chunks[-1] = (
            candidate_last
        )

    return chunks


# ============================================================
# CHILD WINDOWS
# ============================================================

def create_child_windows(
    units,
    max_tokens,
    overlap_units=1
):
    """
    Parent içerisinden overlap'lı child windows üretir.
    """

    windows = []

    n = len(units)

    if n == 0:
        return windows

    start = 0

    while start < n:

        end = start

        while end < n:

            candidate = units[
                start:
                end + 1
            ]

            if (
                units_token_count(
                    candidate
                )
                <= max_tokens
            ):

                end += 1

            else:
                break

        if end == start:
            end = (
                start + 1
            )

        windows.append(
            [
                start,
                end
            ]
        )

        if end >= n:
            break

        current_length = (
            end - start
        )

        if (
            overlap_units > 0
            and current_length
            > overlap_units
        ):

            next_start = (
                end
                - overlap_units
            )

        else:

            next_start = end

        if (
            next_start <= start
        ):

            next_start = (
                start + 1
            )

        start = next_start

    return windows


# ============================================================
# CHILD TAIL REBALANCING
# ============================================================

def rebalance_child_tail(
    units,
    windows,
    min_tokens,
    max_tokens,
    overlap_units
):
    """
    Son child minimum hedefin altında kalırsa
    boundary yeniden düzenlenir.
    """

    if len(windows) < 2:
        return windows

    windows = [
        window.copy()
        for window in windows
    ]

    while len(windows) >= 2:

        last_start, last_end = (
            windows[-1]
        )

        last_tokens = (
            units_token_count(
                units[
                    last_start:
                    last_end
                ]
            )
        )

        if (
            last_tokens
            >= min_tokens
        ):
            break

        prev_start, prev_end = (
            windows[-2]
        )

        # ----------------------------------------------------
        # Son iki child birleşebiliyor mu?
        # ----------------------------------------------------

        union_start = (
            prev_start
        )

        union_end = (
            last_end
        )

        union_tokens = (
            units_token_count(
                units[
                    union_start:
                    union_end
                ]
            )
        )

        if (
            union_tokens
            <= max_tokens
        ):

            windows[-2] = [
                union_start,
                union_end
            ]

            windows.pop()

            continue

        # ----------------------------------------------------
        # Boundary sola kaydır
        # ----------------------------------------------------

        candidate_prev_end = (
            prev_end - 1
        )

        if (
            candidate_prev_end
            - prev_start
            <= overlap_units
        ):
            break

        candidate_last_start = (
            candidate_prev_end
            - overlap_units
        )

        if (
            candidate_last_start
            < 0
        ):
            break

        candidate_previous_tokens = (
            units_token_count(
                units[
                    prev_start:
                    candidate_prev_end
                ]
            )
        )

        candidate_last_tokens = (
            units_token_count(
                units[
                    candidate_last_start:
                    last_end
                ]
            )
        )

        if (
            candidate_previous_tokens
            < min_tokens
        ):
            break

        if (
            candidate_last_tokens
            > max_tokens
        ):
            break

        windows[-2] = [
            prev_start,
            candidate_prev_end
        ]

        windows[-1] = [
            candidate_last_start,
            last_end
        ]

    return windows


# ============================================================
# ARTICLE -> PARENT
# ============================================================

def create_parent_chunks(
    article_text
):
    """
    Makaleden parent chunk'lar oluşturur.
    """

    semantic_units = (
        create_semantic_units(
            article_text
        )
    )

    if not semantic_units:
        return []

    parents = (
        pack_units_no_overlap(
            semantic_units,
            PARENT_MAX_TOKENS
        )
    )

    parents = (
        rebalance_parent_tail(
            parents,
            min_tokens=MIN_PARENT_TOKENS,
            max_tokens=PARENT_MAX_TOKENS
        )
    )

    return parents


# ============================================================
# PARENT -> CHILD
# ============================================================

def create_child_chunks(
    parent_units
):
    """
    Parent içinden overlap'lı child chunk'lar oluşturur.
    """

    windows = (
        create_child_windows(
            units=parent_units,
            max_tokens=CHILD_MAX_TOKENS,
            overlap_units=CHILD_OVERLAP_UNITS
        )
    )

    windows = (
        rebalance_child_tail(
            units=parent_units,
            windows=windows,
            min_tokens=MIN_CHILD_TOKENS,
            max_tokens=CHILD_MAX_TOKENS,
            overlap_units=CHILD_OVERLAP_UNITS
        )
    )

    children = []

    for start, end in windows:

        child_units = (
            parent_units[
                start:end
            ]
        )

        children.append(
            child_units
        )

    return children


# ============================================================
# INPUT KONTROLÜ
# ============================================================

if not INPUT_FILE.exists():

    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı.\n"
        "Önce 01_collect_articles.py çalıştırılmalıdır."
    )


# ============================================================
# VERİYİ OKU
# ============================================================

print(
    "\n500 makale okunuyor..."
)

articles = pd.read_parquet(
    INPUT_FILE
)

print(
    f"Makale sayısı: {len(articles)}"
)


# ============================================================
# CHUNKING
# ============================================================

print(
    "\nParent-Child chunking başlıyor...\n"
)

rows = []


for article_number, (_, article) in enumerate(
    articles.iterrows(),
    start=1
):

    article_id = str(
        article["parent_id"]
    ).strip()


    title = (
        str(article["title"]).strip()
        if pd.notna(article["title"])
        else ""
    )


    url = (
        str(article["url"]).strip()
        if pd.notna(article["url"])
        else ""
    )


    source = ""

    if (
        "__source" in article.index
        and pd.notna(
            article["__source"]
        )
    ):

        source = str(
            article["__source"]
        ).strip()


    article_text = (
        clean_text(
            article["text"]
        )
    )


    if not article_text:

        print(
            f"UYARI: {article_id} boş olduğu için atlandı."
        )

        continue


    # ========================================================
    # PARENT'LAR
    # ========================================================

    parent_chunks = (
        create_parent_chunks(
            article_text
        )
    )


    for parent_index, parent_units in enumerate(
        parent_chunks,
        start=1
    ):

        parent_id = (
            f"{article_id}"
            f"_parent_{parent_index:03d}"
        )


        parent_text = (
            join_units(
                parent_units
            )
        )


        parent_token_count = (
            count_tokens(
                parent_text
            )
        )


        # ====================================================
        # CHILD'LAR
        # ====================================================

        child_chunks = (
            create_child_chunks(
                parent_units
            )
        )


        for child_index, child_units in enumerate(
            child_chunks,
            start=1
        ):

            child_id = (
                f"{parent_id}"
                f"_child_{child_index:03d}"
            )


            chunk_text = (
                join_units(
                    child_units
                )
            )


            chunk_token_count = (
                count_tokens(
                    chunk_text
                )
            )


            rows.append(
                {
                    "article_id": (
                        article_id
                    ),

                    "parent_id": (
                        parent_id
                    ),

                    "parent_index": (
                        parent_index
                    ),

                    "child_id": (
                        child_id
                    ),

                    "child_index": (
                        child_index
                    ),

                    "url": (
                        url
                    ),

                    "title": (
                        title
                    ),

                    "__source": (
                        source
                    ),

                    "parent_text": (
                        parent_text
                    ),

                    "chunk_text": (
                        chunk_text
                    ),

                    "parent_token_count": (
                        parent_token_count
                    ),

                    "chunk_token_count": (
                        chunk_token_count
                    ),
                }
            )


    # ========================================================
    # PROGRESS
    # ========================================================

    if (
        article_number == 1
        or article_number % 25 == 0
        or article_number == len(articles)
    ):

        print(
            f"{article_number}/"
            f"{len(articles)} makale işlendi."
        )


# ============================================================
# DATAFRAME
# ============================================================

chunks_df = pd.DataFrame(
    rows
)


if chunks_df.empty:

    raise RuntimeError(
        "Hiç child chunk oluşturulamadı."
    )


# ============================================================
# VALIDATION
# ============================================================

too_large_parents = (
    chunks_df[
        chunks_df[
            "parent_token_count"
        ]
        > PARENT_MAX_TOKENS
    ]
)


too_large_children = (
    chunks_df[
        chunks_df[
            "chunk_token_count"
        ]
        > CHILD_MAX_TOKENS
    ]
)


empty_children = (
    chunks_df[
        chunks_df[
            "chunk_text"
        ]
        .astype(str)
        .str.strip()
        .eq("")
    ]
)


duplicate_child_ids = (
    chunks_df[
        chunks_df[
            "child_id"
        ]
        .duplicated(
            keep=False
        )
    ]
)


if len(too_large_parents) > 0:

    raise RuntimeError(
        f"{len(too_large_parents)} parent "
        f"{PARENT_MAX_TOKENS} token sınırını aşıyor."
    )


if len(too_large_children) > 0:

    raise RuntimeError(
        f"{len(too_large_children)} child "
        f"{CHILD_MAX_TOKENS} token sınırını aşıyor."
    )


if len(empty_children) > 0:

    raise RuntimeError(
        f"{len(empty_children)} boş child bulundu."
    )


if len(duplicate_child_ids) > 0:

    raise RuntimeError(
        "Duplicate child_id bulundu."
    )


# ============================================================
# KAYDET
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


chunks_df.to_parquet(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# İSTATİSTİKLER
# ============================================================

article_count = (
    chunks_df[
        "article_id"
    ]
    .nunique()
)


parent_count = (
    chunks_df[
        "parent_id"
    ]
    .nunique()
)


child_count = len(
    chunks_df
)


parent_stats_df = (
    chunks_df[
        [
            "parent_id",
            "parent_token_count"
        ]
    ]
    .drop_duplicates(
        subset=[
            "parent_id"
        ]
    )
)


small_parent_count = len(
    parent_stats_df[
        parent_stats_df[
            "parent_token_count"
        ]
        < MIN_PARENT_TOKENS
    ]
)


small_child_count = len(
    chunks_df[
        chunks_df[
            "chunk_token_count"
        ]
        < MIN_CHILD_TOKENS
    ]
)


children_per_parent = (
    chunks_df
    .groupby(
        "parent_id"
    )
    .size()
)


# ============================================================
# SONUÇ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "PARENT - CHILD CHUNKING TAMAMLANDI"
)

print(
    "=" * 70
)


print(
    f"\nMakale sayısı : "
    f"{article_count}"
)

print(
    f"Parent sayısı : "
    f"{parent_count}"
)

print(
    f"Child sayısı  : "
    f"{child_count}"
)

print(
    f"Çıktı dosyası : "
    f"{OUTPUT_FILE}"
)


print(
    "\n"
    + "-" * 70
)


print(
    f"Parent max token : "
    f"{PARENT_MAX_TOKENS}"
)

print(
    f"Parent min hedef : "
    f"{MIN_PARENT_TOKENS}"
)

print(
    f"Child max token  : "
    f"{CHILD_MAX_TOKENS}"
)

print(
    f"Child min hedef  : "
    f"{MIN_CHILD_TOKENS}"
)

print(
    f"Child overlap    : "
    f"{CHILD_OVERLAP_UNITS} semantic unit"
)


# ============================================================
# PARENT TOKEN İSTATİSTİKLERİ
# ============================================================

print(
    "\nParent token istatistikleri:"
)

print(
    parent_stats_df[
        "parent_token_count"
    ]
    .describe()
    .round(2)
)


# ============================================================
# CHILD TOKEN İSTATİSTİKLERİ
# ============================================================

print(
    "\nChild token istatistikleri:"
)

print(
    chunks_df[
        "chunk_token_count"
    ]
    .describe()
    .round(2)
)


# ============================================================
# CHILD / PARENT
# ============================================================

print(
    "\nParent başına child sayısı:"
)

print(
    children_per_parent
    .describe()
    .round(2)
)


# ============================================================
# MINIMUM HEDEFLER
# ============================================================

print(
    "\n"
    + "-" * 70
)


print(
    f"{MIN_PARENT_TOKENS} tokendan küçük "
    f"parent sayısı: "
    f"{small_parent_count}"
)


print(
    f"{MIN_CHILD_TOKENS} tokendan küçük "
    f"child sayısı: "
    f"{small_child_count}"
)


# ============================================================
# CLEANING İSTATİSTİKLERİ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "TEXT CLEANING İSTATİSTİKLERİ"
)

print(
    "=" * 70
)


print(
    "\nKaldırılan adjacent duplicate phrase sayısı: "
    f"{CLEANING_STATS['duplicate_phrases_removed']}"
)


print(
    "Kaldırılan birebir duplicate segment sayısı: "
    f"{CLEANING_STATS['duplicate_segments_removed']}"
)


print(
    "Boundary'de kaldırılan duplicate phrase sayısı: "
    f"{CLEANING_STATS['boundary_duplicate_phrases_removed']}"
)


print(
    "Boundary'de kaldırılan duplicate kelime sayısı: "
    f"{CLEANING_STATS['boundary_duplicate_words_removed']}"
)


print(
    "Navigation temizlenen makale sayısı: "
    f"{CLEANING_STATS['articles_with_navigation_removed']}"
)


print(
    "Kaldırılan navigation blok sayısı: "
    f"{CLEANING_STATS['navigation_blocks_removed']}"
)


print(
    "Kaldırılan navigation item sayısı: "
    f"{CLEANING_STATS['navigation_items_removed']}"
)


print(
    "Kaldırılan navigation soru sayısı: "
    f"{CLEANING_STATS['navigation_questions_removed']}"
)


# ============================================================
# ÖRNEK CHILD
# ============================================================

example = (
    chunks_df.iloc[0]
)


print(
    "\n"
    + "=" * 70
)

print(
    "ÖRNEK CHILD"
)

print(
    "=" * 70
)


print(
    f"""
Article ID   : {example['article_id']}
Parent ID    : {example['parent_id']}
Child ID     : {example['child_id']}
Başlık       : {example['title']}

Parent token : {example['parent_token_count']}
Child token  : {example['chunk_token_count']}

Child text:

{example['chunk_text']}
"""
)


print(
    "\nTamamlandı."
)