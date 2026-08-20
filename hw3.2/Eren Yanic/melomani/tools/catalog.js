// Catalogue tools — the read side.
//
// These are thin on purpose: argument shaping happens in agent/router.js and
// every query lives in db/repository.js. What belongs here is the mapping from
// "what the model asked for" to "what the repository takes".

import { searchAlbums, getAlbumDetails, recommendAlbums } from '../db/repository.js';

export const catalogTools = {
  search_albums(args, { db }) {
    return searchAlbums(db, args);
  },

  get_album_details(args, { db }) {
    return getAlbumDetails(db, args);
  },

  recommend_albums(args, { db }) {
    return recommendAlbums(db, {
      liked_artists: args.liked_artists ?? [],
      liked_albums: args.liked_albums ?? [],
      genres: args.genres ?? [],
      moods: args.moods ?? [],
      decade: args.decade ?? null,
      limit: args.limit ?? 5,
    });
  },
};
