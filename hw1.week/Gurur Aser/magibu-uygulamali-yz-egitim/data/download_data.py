import os
import pandas as pd
from datasets import load_dataset

def preprocess_title(title: str) -> str:
    # Standard lowercasing (since the dataset is primarily English/multilingual)
    title = title.lower()
    # Normalize whitespace (replace multiple spaces/tabs with a single space)
    title = " ".join(title.split())
    return title

def main():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Data directory: {data_dir}")

    print("Downloading Pablinho/movies-dataset from Hugging Face...")
    # Load dataset
    dataset = load_dataset("Pablinho/movies-dataset", split="train")
    
    # Convert to pandas DataFrame for easy CSV saving
    df = dataset.to_pandas()
    
    # Save full dataset
    csv_path = os.path.join(data_dir, "movies_dataset.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Full dataset saved to: {csv_path}")
    print(f"Columns: {list(df.columns)}")
    print(f"Number of rows: {len(df)}")
    
    # Check for title column (usually 'title' or 'original_title')
    title_col = 'title' if 'title' in df.columns else ('original_title' if 'original_title' in df.columns else None)
    if not title_col:
        # Fallback to check lowercase or similar
        for col in df.columns:
            if 'title' in col.lower():
                title_col = col
                break
                
    if title_col:
        print(f"Using column '{title_col}' for movie titles.")
        # Extract titles, drop na
        raw_titles = df[title_col].dropna().astype(str).tolist()
        
        # Preprocess each title
        processed_titles = [preprocess_title(t) for t in raw_titles]
        
        # Remove empty strings and deduplicate
        processed_titles = [t for t in processed_titles if t]
        unique_titles = sorted(list(set(processed_titles)))
        
        # Save titles to a txt file (one title per line) for easy tokenizer training
        titles_path = os.path.join(data_dir, "movie_titles.txt")
        with open(titles_path, "w", encoding="utf-8") as f:
            for title in unique_titles:
                f.write(title + "\n")
        print(f"Movie titles preprocessed and saved to: {titles_path}")
        print(f"Total titles: {len(raw_titles)} -> Unique preprocessed titles: {len(unique_titles)}")
        
        # Clean up CSV file as requested
        if os.path.exists(csv_path):
            os.remove(csv_path)
            print(f"Cleaned up temporary CSV file: {csv_path}")
    else:
        print("Warning: Could not find a title column in the dataset.")

if __name__ == "__main__":
    main()
