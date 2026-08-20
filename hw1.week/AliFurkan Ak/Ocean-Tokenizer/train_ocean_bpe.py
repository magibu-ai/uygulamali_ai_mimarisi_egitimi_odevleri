import os
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.decoders import ByteLevel as ByteLevelDecoder

def train_tokenizer(corpus_path: str, output_path: str, vocab_size: int = 1000):
    """
    Trains a Byte-Level BPE (BBPE) tokenizer on the provided corpus text file
    and saves the resulting configuration/vocabulary to a JSON file.
    """
    if not os.path.exists(corpus_path):
        raise FileNotFoundError(f"Corpus file not found at {corpus_path}")

    print(f"Loading corpus from '{corpus_path}'...")
    
    # 1. Initialize an empty BPE model with a default unknown token if needed
    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    
    # 2. Configure ByteLevel pre-tokenizer and decoder
    # ByteLevel splits text into bytes, meaning any character (even emojis/unicode)
    # can be represented, eliminating Out-Of-Vocabulary (OOV) errors.
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()
    
    # 3. Define the trainer with vocab size and special tokens
    special_tokens = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=special_tokens,
        initial_alphabet=ByteLevel.alphabet()
    )
    
    # 4. Train the tokenizer
    print(f"Training BPE tokenizer (Vocab size target: {vocab_size})...")
    tokenizer.train([corpus_path], trainer=trainer)
    
    # 5. Save the trained model to JSON
    tokenizer.save(output_path)
    print(f"Tokenizer training complete. Saved configuration to '{output_path}'.")

def test_tokenizer(tokenizer_path: str):
    """
    Loads the trained tokenizer from the JSON file and runs a quick
    encode/decode test to verify its correctness.
    """
    print("\n--- Testing Tokenizer Configuration ---")
    if not os.path.exists(tokenizer_path):
        raise FileNotFoundError(f"Tokenizer JSON file not found at {tokenizer_path}")

    # Load tokenizer from the saved JSON file
    tokenizer = Tokenizer.from_file(tokenizer_path)
    
    # Sample text for testing (using content from the corpus)
    sample_text = "The ocean contains 97% of Earth's water and is essential to life."
    
    # Safe printing helper for Windows console encoding issues (e.g. cp1254 / cp1252)
    def safe_print(label, text_or_list):
        try:
            print(f"{label:<16} {text_or_list}")
        except UnicodeEncodeError:
            if isinstance(text_or_list, list):
                safe_list = [t.encode('ascii', errors='backslashreplace').decode('ascii') for t in text_or_list]
                print(f"{label:<16} (Safe ASCII): {safe_list}")
            else:
                safe_str = str(text_or_list).encode('ascii', errors='backslashreplace').decode('ascii')
                print(f"{label:<16} (Safe ASCII): {safe_str}")

    safe_print("Original Text", sample_text)
    
    # Encode text to IDs and tokens
    encoded = tokenizer.encode(sample_text)
    safe_print("Encoded IDs", encoded.ids)
    safe_print("Encoded Tokens", encoded.tokens)
    
    # Decode IDs back to text
    decoded = tokenizer.decode(encoded.ids)
    safe_print("Decoded Text", decoded)
    
    # Verify that decoding matches original text
    assert decoded.strip() == sample_text.strip(), "Error: Decoded text does not match original text!"
    print("\nSuccess: Tokenizer successfully encoded and decoded sample text without losses!")

if __name__ == "__main__":
    # Define paths
    corpus_file = os.path.join("data", "ocean_corpus.txt")
    output_json = "ocean_bpe_tokenizer.json"
    
    # Run training
    train_tokenizer(corpus_file, output_json, vocab_size=1000)
    
    # Run test
    test_tokenizer(output_json)
