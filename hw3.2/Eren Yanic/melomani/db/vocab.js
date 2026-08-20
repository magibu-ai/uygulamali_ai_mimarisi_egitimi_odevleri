// Vocabulary normalisation.
//
// The catalogue's tags are English and fixed. A customer speaking Turkish says
// "hüzünlü", and the model passes that through verbatim — as observed against
// every model tested. An English speaker says "sad" or "dark", which are just
// as absent from the tag table.
//
// Rather than instruct the model harder and hope, the incoming terms are mapped
// onto the stored vocabulary here, at the boundary. An unrecognised term is
// passed through unchanged: it will simply score nothing, which is honest.

const MOODS = {
  // Turkish
  'hüzünlü': 'melancholic', 'huzunlu': 'melancholic', 'hüzün': 'melancholic',
  'melankolik': 'melancholic', 'kasvetli': 'melancholic', 'karamsar': 'melancholic',
  'gece': 'nocturnal', 'gecelik': 'nocturnal', 'karanlık': 'nocturnal', 'karanlik': 'nocturnal',
  'atmosferik': 'atmospheric', 'hipnotik': 'hypnotic', 'hipnotize': 'hypnotic',
  'sakin': 'sparse', 'dingin': 'sparse', 'yalın': 'sparse', 'yalin': 'sparse',
  'minimal': 'minimal', 'yoğun': 'dense', 'yogun': 'dense',
  'sıcak': 'warm', 'sicak': 'warm', 'soğuk': 'cold', 'soguk': 'cold',
  'danslık': 'danceable', 'dansedilebilir': 'danceable', 'hareketli': 'danceable',
  'deneysel': 'experimental', 'politik': 'political', 'siyasi': 'political',
  'protest': 'protest', 'romantik': 'romantic', 'psikedelik': 'psychedelic',
  'sinematik': 'cinematic', 'enstrümantal': 'instrumental', 'enstrumantal': 'instrumental',
  'gürültülü': 'noise', 'gurultulu': 'noise', 'gitar': 'guitar-driven',
  'vokal': 'vocal-led', 'doğaçlama': 'improvisation', 'dogaclama': 'improvisation',
  'nostaljik': 'nostalgic', 'ruhani': 'spiritual', 'manevi': 'spiritual',
  'canlı': 'live', 'canli': 'live', 'groove': 'groove',

  // Metal and rock, Turkish
  'ağır': 'heavy', 'agir': 'heavy', 'sert': 'heavy', 'kaba': 'heavy',
  'hızlı': 'fast', 'hizli': 'fast', 'çabuk': 'fast',
  'teknik': 'technical', 'karmaşık': 'technical', 'karmasik': 'technical',
  'destansı': 'epic', 'destansi': 'epic', 'epik': 'epic', 'görkemli': 'epic',
  'ham': 'raw', 'kaba saba': 'raw', 'lofi': 'lo-fi',
  'ilerici': 'progressive', 'progresif': 'progressive',
  'marşvari': 'anthemic', 'marsvari': 'anthemic',
  'okült': 'occult', 'okult': 'occult', 'şeytani': 'occult', 'seytani': 'occult',
  'blues': 'blues-based',

  // English variants that are not themselves tags
  'sad': 'melancholic', 'moody': 'melancholic', 'sombre': 'melancholic', 'somber': 'melancholic',
  'wistful': 'melancholic', 'bleak': 'melancholic',
  'dark': 'nocturnal', 'late-night': 'nocturnal', 'night': 'nocturnal',
  'chill': 'sparse', 'calm': 'sparse', 'quiet': 'sparse', 'stripped-back': 'sparse',
  'dreamy': 'lush', 'ethereal': 'lush', 'shimmering': 'lush',
  'mellow': 'warm', 'soulful': 'warm',
  'upbeat': 'danceable', 'energetic': 'danceable', 'funky': 'groove',
  'abrasive': 'noise', 'loud': 'noise',
  'weird': 'experimental', 'avant-garde': 'experimental', 'trippy': 'psychedelic',
  'cinematic': 'cinematic', 'filmic': 'cinematic',
  'spiritual': 'spiritual', 'political': 'political',

  // Metal and rock, English. "aggressive" points at `heavy` rather than `noise`
  // now that the catalogue has metal in it — a listener asking for something
  // aggressive wants Slayer, not My Bloody Valentine.
  'aggressive': 'heavy', 'brutal': 'heavy', 'crushing': 'heavy', 'hard': 'heavy',
  'headbanging': 'heavy', 'metallic': 'heavy',
  'blazing': 'fast', 'relentless': 'fast', 'frantic': 'fast', 'speedy': 'fast',
  'virtuosic': 'technical', 'complex': 'technical', 'intricate': 'technical',
  'grand': 'epic', 'majestic': 'epic', 'sprawling': 'epic',
  'primitive': 'raw', 'gritty': 'raw', 'unpolished': 'raw',
  'prog': 'progressive', 'proggy': 'progressive',
  'anthem': 'anthemic', 'singalong': 'anthemic',
  'satanic': 'occult', 'evil': 'occult', 'demonic': 'occult', 'blasphemous': 'occult',
  'bluesy': 'blues-based', 'blues-rock': 'blues-based',
};

const GENRES = {
  'caz': 'jazz', 'klasik': 'jazz', 'elektronik': 'ambient-techno', 'elektronik müzik': 'ambient-techno',
  'hiphop': 'hip-hop', 'hip hop': 'hip-hop', 'rap': 'hip-hop',
  'anadolu rock': 'anadolu-rock', 'anadolu pop': 'anadolu-rock', 'türk rock': 'anadolu-rock',
  'triphop': 'trip-hop', 'trip hop': 'trip-hop',
  'postpunk': 'post-punk', 'post punk': 'post-punk',
  'dream pop': 'dream-pop', 'dreampop': 'dream-pop',
  'ruh': 'soul', 'funk': 'jazz-funk', 'ortam': 'ambient',

  // Metal. Genre strings all end in "-metal", so a search_albums call with
  // "metal" reaches the whole family through LIKE; these map the spaced and
  // Turkish spellings onto the exact values recommend_albums matches on.
  'black metal': 'black-metal', 'blackmetal': 'black-metal', 'siyah metal': 'black-metal',
  'death metal': 'death-metal', 'deathmetal': 'death-metal', 'ölüm metal': 'death-metal',
  'thrash metal': 'thrash-metal', 'thrash': 'thrash-metal', 'traş metal': 'thrash-metal',
  'progressive metal': 'progressive-metal', 'prog metal': 'progressive-metal',
  'progresif metal': 'progressive-metal',
  'heavy metal': 'heavy-metal', 'ağır metal': 'heavy-metal', 'agir metal': 'heavy-metal',
  'doom metal': 'doom-metal', 'doom': 'doom-metal',
  'groove metal': 'groove-metal',

  // Rock
  'prog rock': 'prog-rock', 'progressive rock': 'prog-rock', 'progresif rock': 'prog-rock',
  'classic rock': 'classic-rock', 'klasik rock': 'classic-rock',
  'hard rock': 'hard-rock', 'sert rock': 'hard-rock',
  'psychedelic rock': 'psych-rock', 'psych rock': 'psych-rock',
  'psikedelik rock': 'psych-rock', 'psikedelik': 'psych-rock',
  'alternatif rock': 'alt-rock', 'alternative rock': 'alt-rock',
  'grunj': 'grunge',
};

function normalise(map, term) {
  if (term == null) return term;
  const key = String(term).trim().toLowerCase();
  return map[key] ?? key;
}

/** Map a mood term onto the stored tag vocabulary. Unknown terms pass through. */
export function normaliseMood(term) {
  return normalise(MOODS, term);
}

/** Map a genre term onto the stored genre vocabulary. Unknown terms pass through. */
export function normaliseGenre(term) {
  return normalise(GENRES, term);
}

/** The tag vocabulary a caller may usefully supply — used in the tool schema. */
export const KNOWN_MOODS = [
  'melancholic', 'nocturnal', 'atmospheric', 'hypnotic', 'lush', 'minimal', 'sparse',
  'dense', 'warm', 'cold', 'danceable', 'groove', 'experimental', 'political',
  'romantic', 'psychedelic', 'cinematic', 'instrumental', 'sampling', 'lo-fi',
  'noise', 'guitar-driven', 'vocal-led', 'improvisation', 'nostalgic', 'spiritual',
  'protest', 'live', 'modal', 'concept-album', 'debut', 'ambient', 'dub',
  'heavy', 'fast', 'technical', 'epic', 'raw', 'progressive', 'anthemic',
  'occult', 'blues-based',
];
