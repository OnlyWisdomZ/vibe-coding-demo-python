import pandas as pd
import os

def check_missing_values(input_file):
    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        return

    print(f"正在读取文件: {input_file} ...")
    try:
        df = pd.read_excel(input_file)
        total_len = len(df)
        print(f"数据加载完成，总记录数: {total_len}")
        
        allowed_missing_cols = [
            'hotelImageUrl', 
            'verifyReason', 
            'postsName', 
            'verifyStatus', 
            'verifyStatusDesc',
            'memberId',
            'tags'
            'headImg'
        ]
        
        print("正在进行缺失值检查...")
        # 找出所有包含缺失值的列
        missing_counts = df.isnull().sum()
        cols_with_missing = missing_counts[missing_counts > 0]
        
        if len(cols_with_missing) == 0:
            print("检查通过: 数据中没有任何缺失值。")
            return
            
        print(f"发现包含缺失值的列：")
        for col, count in cols_with_missing.items():
            print(f"  - {col}: 缺失 {count} 条")
            
        # 检查是否所有包含缺失值的列都在允许的列表中
        unauthorized_missing = [col for col in cols_with_missing.index if col not in allowed_missing_cols]
        
        if len(unauthorized_missing) == 0:
            print("\n检查通过: 所有包含缺失值的列均在允许的名单内。没有非预期的缺失值。")
        else:
            print("\n【检查失败】: 发现以下不允许包含缺失值的列存在缺失值！")
            for col in unauthorized_missing:
                print(f"  - {col}: 缺失 {missing_counts[col]} 条")
                
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == "__main__":
    # 使用当前文件相对于脚本运行位置的路径
    input_path = "backend/hotel_comments_cleaned.xlsx"
    
    # 如果脚本是在backend目录下直接运行的，调整路径
    if os.path.basename(os.getcwd()) == "backend":
        input_path = "hotel_comments_cleaned.xlsx"
        
    check_missing_values(input_path)
