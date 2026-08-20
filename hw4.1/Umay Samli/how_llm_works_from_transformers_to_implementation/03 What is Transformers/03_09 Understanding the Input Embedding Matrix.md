For every token, the model adds its token embedding and positional embedding. Stacking these vectors produces the **input embedding matrix**.

For the five-token sentence “The next day is bright”, using eight-dimensional embeddings gives a matrix with shape `(5, 8)`:

- Each of the 5 rows represents one token.
- Each of the 8 columns represents one learned embedding feature.

In general, the shape is `(sequence_length, embedding_dimension)`, or `(batch_size, sequence_length, embedding_dimension)` when several sequences are processed together. The embedding dimension is a model design choice: larger dimensions can hold more nuanced features but require more parameters and computation.

At this point, each row contains token identity and position, but it still lacks information from neighboring tokens. For example, the initial vector for “day” does not yet know that “next” provides temporal context or that “bright” describes it. [[03_10 From Embeddings to Queries, Keys and Values|Query, key, and value projections]] begin the transformation from these isolated input vectors into contextual representations.
