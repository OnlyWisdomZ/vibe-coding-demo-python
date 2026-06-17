import pandas as pd
import os

def count_room_types(input_file):
    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        return
    print(f"正在读取文件: {input_file} ...")
    try:
        df = pd.read_excel(input_file)
        num_room_types = df['房型名称'].dropna().nunique()
        print(f"房型种类数: {num_room_types}")
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == "__main__":
    input_path = "backend/hotel_comments_cleaned.xlsx"
    if os.path.basename(os.getcwd()) == "backend":
        input_path = "hotel_comments_cleaned.xlsx"
    count_room_types(input_path)
