import pandas as pd
import os

def deduplicate_data(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} does not exist.")
        return
    print(f"正在读取文件: {input_file} ...")
    try:
        df = pd.read_excel(input_file)
        original_len = len(df)
        print("正在进行数据去重...")
        # 去除完全重复的行
        df_dedup = df.drop_duplicates()
        new_len = len(df_dedup)
        print(f"去重完成: 删除了 {original_len - new_len} 条重复记录。当前剩余 {new_len} 条记录。")
        print(f"正在保存至: {output_file} ...")
        df_dedup.to_excel(output_file, index=False)
        print("保存成功！")
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == "__main__":
    input_path = "backend/hotel_comments_final.xlsx"
    output_path = "backend/hotel_comments_dedup.xlsx"
    if os.path.basename(os.getcwd()) == "backend":
        input_path = "hotel_comments_final.xlsx"
        output_path = "hotel_comments_dedup.xlsx"
    deduplicate_data(input_path, output_path)

