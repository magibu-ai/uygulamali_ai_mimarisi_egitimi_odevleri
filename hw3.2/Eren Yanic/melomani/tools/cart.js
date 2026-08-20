// Cart and order tools — the write side.
//
// `session_id` comes from the router's context, never from the model. That is
// what stops one visitor from adding to, or reading, another visitor's cart.

import { addToCart, checkout, checkOrderStatus, viewCart } from '../db/repository.js';

export const cartTools = {
  add_to_cart(args, { db, session_id }) {
    return addToCart(db, {
      session_id,
      album_id: args.album_id,
      quantity: args.quantity ?? 1,
    });
  },

  /**
   * Checkout is gated: the first call in a customer turn returns a preview and
   * commits nothing. Only a call in a *later* turn places the order.
   *
   * This is a structural guarantee rather than a prompt instruction, and it
   * exists because a prompt instruction was observed to fail. Asked merely what
   * was on a record, Qwen2.5-7B added it to the cart and checked out in the same
   * turn — an order the customer never requested. Because a customer turn can
   * only end when the model stops calling tools and replies, requiring a second
   * turn means the preview must reach the customer, and they must answer,
   * before anything is bought.
   */
  checkout(args, context) {
    const { db, session_id, turnId } = context;
    const gate = context.gate ?? (context.gate = {});

    if (gate.previewTurn == null || gate.previewTurn === turnId) {
      const cart = viewCart(db, { session_id });
      if (cart.item_count === 0) {
        return { ok: false, error: 'EMPTY_CART', message: 'The cart is empty, so there is nothing to check out.' };
      }
      gate.previewTurn = turnId;
      return {
        ok: false,
        error: 'CONFIRMATION_REQUIRED',
        message:
          'Nothing has been ordered yet. Show the customer exactly this basket and total, ask them to confirm, '
          + 'and call checkout again only after they have answered.',
        preview: {
          items: cart.items,
          item_count: cart.item_count,
          total_display: cart.total_display,
          customer_name: args.customer_name ?? null,
        },
      };
    }

    const result = checkout(db, { session_id, customer_name: args.customer_name });
    if (result.ok) gate.previewTurn = null;
    return result;
  },

  check_order_status(args, { db, session_id }) {
    return checkOrderStatus(db, { session_id, order_id: args.order_id });
  },
};
