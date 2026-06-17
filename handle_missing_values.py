import pandas as pd
import os

def handle_missing_values(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        return
    print(f"正在读取文件: {input_file} ...")
    try:
        df = pd.read_excel(input_file)
        original_len = len(df)
        # 允许有缺失值的列
        allowed_missing_cols = [
            '酒店图片URL', 
            '审核原因', 
            '评价人名称', 
            '审核状态码', 
            '审核状态描述',
            '会员ID',
            '评价标签',
            '用户头像'
        ]
        # 要先找出哪些列是全空的，将它们加入允许缺失的名单中 不参与检查
        all_null_cols = df.columns[df.isnull().all()].tolist()
        print(f"发现完全为空的列: {all_null_cols}，这些列不参与缺失值检查。")
        # 将全空的列也加入允许缺失的列名中
        allowed_missing_cols.extend(all_null_cols)
        # 检查哪些允许缺失的列确实存在于数据中，避免报错
        existing_allowed_cols = [col for col in allowed_missing_cols if col in df.columns]
        # 需要检查缺失值的列（即除了允许缺失的列之外的所有列）
        cols_to_check = [col for col in df.columns if col not in existing_allowed_cols]
        print(f"参与缺失值检查的列共有 {len(cols_to_check)} 个。")
        print("正在处理缺失值...")
        # 删除在必须包含数据的列中有缺失值的行
        df_cleaned = df.dropna(subset=cols_to_check)
        new_len = len(df_cleaned)
        print(f"缺失值处理完成: 删除了 {original_len - new_len} 条包含缺失值的记录。当前剩余 {new_len} 条记录。")
        print(f"正在保存至: {output_file} ...")
        df_cleaned.to_excel(output_file, index=False)
        print("保存成功！")
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == "__main__":
    input_path = "backend/hotel_comments_dedup.xlsx"
    output_path = "backend/hotel_comments_cleaned.xlsx"
    if os.path.basename(os.getcwd()) == "backend":
        input_path = "hotel_comments_dedup.xlsx"
        output_path = "hotel_comments_cleaned.xlsx"
    handle_missing_values(input_path, output_path)
