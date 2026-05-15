import pandas as pd
import os

def check_duplicates(input_file):
    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        return

    print(f"正在读取文件: {input_file} ...")
    try:
        df = pd.read_excel(input_file)
        total_len = len(df)
        
        print(f"数据加载完成，总记录数: {total_len}")
        
        print("正在进行重复值检查...")
        # 检查完全重复的行
        duplicates = df[df.duplicated(keep=False)]
        num_duplicates = len(duplicates)
        
        if num_duplicates == 0:
            print("检查通过: 数据中没有任何完全重复的记录。")
        else:
            # 计算去重后应该剩下的条数，即 duplicated(keep='first') 为 True 的数量
            num_duplicate_groups = len(df[df.duplicated(keep='first')])
            print(f"【发现重复】: 数据中存在完全重复的记录！")
            print(f"共有 {num_duplicates} 行数据参与了重复（分属 {num_duplicate_groups} 个重复组）。")
            
            # 显示前几条重复数据供参考
            print("\n重复数据展示 (前100条):")
            print(duplicates.head(100))
            
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == "__main__":
    input_path = "backend/hotel_comments_dedup.xlsx"

    if os.path.basename(os.getcwd()) == "backend":
        input_path = "hotel_comments_dedup.xlsx"
        
    check_duplicates(input_path)
