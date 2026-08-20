from tokenizers import Tokenizer
from tokenizers.decoders import ByteLevel as ByteLevelDecoder
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.trainers import BpeTrainer
from transformers import AutoTokenizer, PreTrainedTokenizerFast

TEXT_FILE = "text.txt"
REPO_ID = "gorkemergune/my-tokenizer"
VOCAB_SIZE = 2 ** 11

SPECIAL_TOKENS = ["<unk>", "<pad>", "<bos>", "<eos>"]


backend = Tokenizer(BPE(unk_token="<unk>"))
backend.pre_tokenizer = ByteLevel(add_prefix_space=False)
backend.decoder = ByteLevelDecoder()

trainer = BpeTrainer(
    vocab_size=VOCAB_SIZE,
    special_tokens=SPECIAL_TOKENS,
    initial_alphabet=ByteLevel.alphabet(),
)
backend.train([TEXT_FILE], trainer)

tokenizer = PreTrainedTokenizerFast(
    tokenizer_object=backend,
    unk_token="<unk>",
    pad_token="<pad>",
    bos_token="<bos>",
    eos_token="<eos>",
)

tokenizer.save_pretrained("my-tokenizer")
tokenizer.push_to_hub(REPO_ID)

loaded = AutoTokenizer.from_pretrained(REPO_ID)
example = "Hello! This is a very small tokenizer example."

token_ids = loaded.encode(example)
print("Tokens:", loaded.convert_ids_to_tokens(token_ids))
print("Token IDs:", token_ids)
print("Decoded:", loaded.decode(token_ids))
