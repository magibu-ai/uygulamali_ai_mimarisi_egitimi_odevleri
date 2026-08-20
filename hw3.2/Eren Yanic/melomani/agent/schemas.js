// JSON Schema definitions for the six tools, in the shape the OpenAI-compatible
// chat-completions API expects. This is the only description of the tools the
// model ever sees.
//
// Two deliberate choices:
//
//   * Write tools take `album_id`, never a title. The model cannot pass a name
//     it invented into the cart, because a name is not an accepted type.
//   * `session_id` and the database handle are not in any schema. They are
//     injected by the router from trusted context, so the model cannot address
//     another visitor's cart or orders.

export const TOOL_SCHEMAS = [
  {
    type: 'function',
    function: {
      name: 'search_albums',
      description:
        'Search the shop catalogue with optional filters. Use this whenever the customer asks what is available, ' +
        'or before adding anything to the cart, to obtain a valid album_id. Returns only albums this shop actually stocks.',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Free text matched against album title, artist name and genre.' },
          artist: { type: 'string', description: 'Filter by artist name.' },
          genre: {
            type: 'string',
            description:
              'Filter by genre. Matching is partial, so "metal" returns every metal subgenre and "rock" every rock one. '
              + 'Stocked genres: trip-hop, post-punk, shoegaze, dream-pop, alt-rock, art-rock, classic-rock, prog-rock, '
              + 'hard-rock, psych-rock, grunge, anadolu-rock, thrash-metal, death-metal, black-metal, progressive-metal, '
              + 'heavy-metal, doom-metal, groove-metal, jazz, jazz-funk, soul, neo-soul, hip-hop, ambient, '
              + 'ambient-techno, idm, dubstep, art-pop.',
          },
          year_from: { type: 'integer', description: 'Earliest release year.' },
          year_to: { type: 'integer', description: 'Latest release year.' },
          max_price_try: { type: 'number', description: 'Maximum price in Turkish lira.' },
          in_stock_only: { type: 'boolean', description: 'When true, omit albums with zero stock.' },
          limit: { type: 'integer', description: 'How many results to return, 1-25. Defaults to 10.' },
        },
        required: [],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'get_album_details',
      description:
        'Full record for one album: tracklist, label, country, descriptive tags, price and current stock. ' +
        'Use when the customer asks what is on a record or wants to know more before buying.',
      parameters: {
        type: 'object',
        properties: {
          album_id: { type: 'integer', description: 'Catalogue id, as returned by search_albums or recommend_albums.' },
        },
        required: ['album_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'recommend_albums',
      description:
        'Recommend albums from this shop based on stated taste. Supply whatever the customer gave you — artists they ' +
        'like, albums they like, genres, or moods. Every result carries a `why` explaining the match; quote that ' +
        'reason rather than inventing your own. Never recommend a record that did not come back from this tool.',
      parameters: {
        type: 'object',
        properties: {
          liked_artists: {
            type: 'array', items: { type: 'string' },
            description: 'Artists the customer says they like.',
          },
          liked_albums: {
            type: 'array', items: { type: 'string' },
            description: 'Album titles the customer says they like.',
          },
          genres: {
            type: 'array', items: { type: 'string' },
            description: 'Genres the customer asked for.',
          },
          moods: {
            type: 'array', items: { type: 'string' },
            description:
              'Mood or style descriptors. Recognised values include: melancholic, nocturnal, atmospheric, hypnotic, ' +
              'lush, minimal, sparse, dense, warm, cold, danceable, groove, experimental, political, romantic, ' +
              'psychedelic, cinematic, instrumental, sampling, lo-fi, noise, guitar-driven, vocal-led, improvisation.',
          },
          decade: { type: 'integer', description: 'Preferred decade as a year, e.g. 1990 for the 1990s.' },
          limit: { type: 'integer', description: 'How many recommendations, 1-10. Defaults to 5.' },
        },
        required: [],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'add_to_cart',
      description:
        'Add copies of an album to the customer\'s cart. Requires a numeric album_id obtained from search_albums or ' +
        'recommend_albums — never guess one. Returns the full cart with a running total.',
      parameters: {
        type: 'object',
        properties: {
          album_id: { type: 'integer', description: 'Catalogue id of the album to add.' },
          quantity: { type: 'integer', description: 'Number of copies. Defaults to 1.' },
        },
        required: ['album_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'checkout',
      description:
        'Place the order for everything currently in the cart. Deducts stock and returns an order_id and the total. ' +
        'Ask the customer for their name first if you do not have it, and confirm they want to order before calling this.',
      parameters: {
        type: 'object',
        properties: {
          customer_name: { type: 'string', description: 'Name to place the order under.' },
        },
        required: ['customer_name'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'check_order_status',
      description:
        'Look up an order placed in this session and report its fulfilment stage. Use when the customer asks about an ' +
        'order they already placed.',
      parameters: {
        type: 'object',
        properties: {
          order_id: { type: 'integer', description: 'The order_id returned by checkout.' },
        },
        required: ['order_id'],
      },
    },
  },
];

export const TOOL_NAMES = TOOL_SCHEMAS.map((t) => t.function.name);
