import sys
from ollama_client import run_conversation

def print_banner():
    print("=" * 65)
    print(" AKILLI TEKSTİL VE ÖRGÜ ASİSTANI (Craft Companion) ")
    print("=" * 65)
    print("El işi, tığ, örgü, ilmek hesabı, birim dönüştürme ve teknik")
    print("terimler hakkında sorular sorabilirsiniz.")
    print("Çıkmak için 'çıkış', 'exit' veya 'q' yazabilirsiniz.")
    print("=" * 65)

def main():
    print_banner()
    conversation_history = []

    while True:
        try:
            user_input = input("\n Kullanıcı: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["çıkış", "exit", "q"]:
                print("\n Örgü Asistanı kapatılıyor. Keyifli örgüler!\n")
                sys.exit(0)

            # Kullanıcı mesajını geçmişe ekle
            conversation_history.append({"role": "user", "content": user_input})

            print("\n Asistan yanıtı hazırlıyor...")

            # Ajan döngüsünü çalıştır
            response = run_conversation(conversation_history)

            # Asistan yanıtını ekrana bas ve geçmişe kaydet
            print(f"\n Asistan:\n{response}")
            conversation_history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            print("\n\n Program kullanıcı tarafından durduruldu.")
            sys.exit(0)
        except Exception as e:
            print(f"\n Bir hata oluştu: {str(e)}")

if __name__ == "__main__":
    main()