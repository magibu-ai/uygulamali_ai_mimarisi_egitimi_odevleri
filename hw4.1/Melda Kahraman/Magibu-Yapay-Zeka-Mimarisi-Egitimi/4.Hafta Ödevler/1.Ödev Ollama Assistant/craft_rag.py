import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

def init_rag_db():
    collection = client.get_or_create_collection(name="craft_knowledge")
    
    if collection.count() == 0:
        documents = [
            "Single Crochet (sc / Sık İğne): Tığı ilmeğe batırın, ipi çekin, tığdaki 2 ilmeği birlikte örün. Amiguruminin temel ilmeğidir.",
            "Half Double Crochet (hdc / Tekli Trabzan / Çakma Sık İğne): Tığa ip dolayın, ilmeğe batın, tığdaki 3 ilmeği tek seferde çekin.",
            "Double Crochet (dc / İkili Trabzan): Tığa ip dolayın, ilmeğe batın, ilmekleri 2'şerli olarak 2 adımda çekin.",
            "Increase (inc / Artırma): Aynı ilmeğin içerisine 2 kez sık iğne (sc) örerek ilmek sayısını artırma işlemidir.",
            "Decrease (dec / Eksiltme): Yan yana iki ilmeğin sadece ön loblarını (FLO) alarak birlikte örme ve ilmek sayısını azaltma işlemidir.",
            "Magic Ring (mr / Sihirli Halka): Amigurumi ve yuvarlak motiflerin merkezini başlatmak için kullanılan, ortası büzülebilir ayarlanabilir halka.",
            "Blocking (Örgü Serme/Ütüleme): Bitmiş örgü parçasını ıslatıp mantar panoya iğneleyerek form kazandırma ve ilmekleri düzeltme işlemi.",
            "Mattress Stitch (Yatak Dikişi): Örgü parçalarını dışarıdan dikiş izi belli olmayacak şekilde elde birleştirme tekniği.",
            "Gauge / Swatch (İlmek Testi): Örgüye başlamadan önce 10x10 cm boyutlarında parça örerek ilmek ve sıra sayısını doğrulama.",
            "Yarn Weight Standartları: Lace (Çok İnce), Fingering (İnce/Çoraplık), DK / Worsted (Orta Kalınlık), Bulky (Çok Kalın)."
        ]
        metadatas = [{"source": "el_isi_rehberi"} for _ in documents]
        ids = [f"doc_{i}" for i in range(len(documents))]
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

def query_rag(query_text: str, n_results: int = 4) -> str: 
    try:
        collection = client.get_or_create_collection(name="craft_knowledge")
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        if results and results.get("documents") and len(results["documents"][0]) > 0:
            found_docs = results["documents"][0]
            return "\n".join([f"- {doc}" for doc in found_docs])
        return "İlgili teknik bilgi veritabanında bulunamadı."
    except Exception as e:
        return f"RAG sorgulama hatası: {str(e)}"
    
if __name__ == "__main__":
    init_rag_db()
    print("ChromaDB el işi veritabanı başarıyla güncellendi.")
