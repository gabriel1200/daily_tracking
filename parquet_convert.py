import pandas as pd
from pathlib import Path

def convert_csv_to_parquet():
    # Define the path to your data folder
    folder_path = Path("careerlogs")
    
    # Check if the directory exists to avoid errors
    if not folder_path.is_dir():
        print(f"Error: The directory '{folder_path}' was not found.")
        return

    # Find all CSV files in the folder
    csv_files = list(folder_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in '{folder_path}'.")
        return
        
    print(f"Found {len(csv_files)} CSV files. Starting conversion...")

    for csv_file in csv_files:
        try:
            # Read the CSV file
            df = pd.read_csv(csv_file)
            
            # Create the Parquet file path by replacing the .csv extension with .parquet
            parquet_file = csv_file.with_suffix(".parquet")
            
            # Save the dataframe to Parquet format
            # index=False prevents pandas from writing row numbers as a new column
            df.to_parquet(parquet_file, engine="pyarrow", index=False)
            
            print(f"Success: {csv_file.name} -> {parquet_file.name}")
            
        except Exception as e:
            print(f"Failed to convert {csv_file.name}: {e}")

    print("Conversion complete!")

if __name__ == "__main__":
    convert_csv_to_parquet()