import pandas as pd

# Danh sách header bạn cung cấp
headers = [
    'Toan_1_10', 'Van_1_10', 'Ly_1_10', 'Hoa_1_10', 'Sinh_1_10', 'Su_1_10', 'Dia_1_10', 'Anh_1_10', 'CD_1_10',
    'Toan_2_10', 'Van_2_10', 'Ly_2_10', 'Hoa_2_10', 'Sinh_2_10', 'Su_2_10', 'Dia_2_10', 'Anh_2_10', 'CD_2_10',
    'Toan_1_11', 'Van_1_11', 'Ly_1_11', 'Hoa_1_11', 'Sinh_1_11', 'Su_1_11', 'Dia_1_11', 'Anh_1_11', 'CD_1_11',
    'Toan_2_11', 'Van_2_11', 'Ly_2_11', 'Hoa_2_11', 'Sinh_2_11', 'Su_2_11', 'Dia_2_11', 'Anh_2_11', 'CD_2_11',
    'Toan_1_12', 'Van_1_12', 'Ly_1_12', 'Hoa_1_12', 'Sinh_1_12', 'Su_1_12', 'Dia_1_12', 'Anh_1_12', 'CD_1_12',
    'Toan_2_12', 'Van_2_12', 'Ly_2_12', 'Hoa_2_12', 'Sinh_2_12', 'Su_2_12', 'Dia_2_12', 'Anh_2_12', 'CD_2_12'
]


names = ['Name',
         'Maths_1_10', 'Literature_1_10', 'Physics_1_10', 'Chemistry_1_10', 'Biology_1_10', 'History_1_10', 'Geography_1_10', 'English_1_10', 'Civic Education_1_10',
         'Maths_2_10', 'Literature_2_10', 'Physics_2_10', 'Chemistry_2_10', 'Biology_2_10', 'History_2_10', 'Geography_2_10', 'English_2_10', 'Civic Education_2_10',
         'Maths_1_11', 'Literature_1_11', 'Physics_1_11', 'Chemistry_1_11', 'Biology_1_11', 'History_1_11', 'Geography_1_11', 'English_1_11', 'Civic Education_1_11',
         'Maths_2_11', 'Literature_2_11', 'Physics_2_11', 'Chemistry_2_11', 'Biology_2_11', 'History_2_11', 'Geography_2_11', 'English_2_11', 'Civic Education_2_11',
         'orphan_and_kiosk',
         'Maths_1_12', 'Literature_1_12', 'Physics_1_12', 'Chemistry_1_12', 'Biology_1_12', 'History_1_12', 'Geography_1_12', 'English_1_12', 'Civic Education_1_12',
         'Maths_2_12', 'Literature_2_12', 'Physics_2_12', 'Chemistry_2_12', 'Biology_2_12', 'History_2_12', 'Geography_2_12', 'English_2_12', 'Civic Education_2_12']

# Đọc file Excel (ví dụ: input.xlsx)
file = "D:\\TaiXuong\\AI project\\EduTwin\\10_11_12_header_removed (2).xlsx"
df = pd.DataFrame(pd.read_excel(file, header=None, sheet_name='10_11_12', names=names)).drop(columns = ['Name','orphan_and_kiosk'], axis=1)
df = df.dropna()  # Xóa các dòng có NaN
# Gán lại tên cột
df.columns = headers

# Xuất ra file Excel mới
df.to_excel("D:/TaiXuong/AI project/EduTwin/10_11_12.xlsx", index=False)