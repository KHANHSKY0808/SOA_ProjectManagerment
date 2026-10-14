Dưới đây là dàn ý chi tiết và lộ trình thực hiện bài tập lớn/đồ án **Hệ thống Quản lý Đồ án Tốt nghiệp theo kiến trúc SOA**, được thiết kế bám sát 100% các tiêu chí đánh giá trong file **[Slide]SOA_baitap.pdf**[1][2]. Dàn ý này được sắp xếp theo một lộ trình 6 bước logic, đi từ khái niệm cơ bản đến triển khai thực tế, giúp người chưa từng làm việc với web framework cũng có thể đọc hiểu và thực hiện từng bước.

---

### **PHẦN 1: NHẬP MÔN &amp; KHÁI NIỆM NỀN TẢNG (Dành cho người chưa biết gì)**

**Mục tiêu:** Giúp thành viên trong nhóm nắm vững bản chất kiến trúc và công nghệ trước khi gõ dòng code đầu tiên.

- **1.1\. Khái niệm Web Framework là gì?**
  - Khái niệm Web Framework: Tập hợp các công cụ, thư viện chuẩn hóa giúp đơn giản hóa quá trình phát triển web thay vì phải viết code thuần[3].
  - Vì sao nên dùng Framework? (Tự động hóa kết nối CSDL, quản lý URL, bảo mật và cấu trúc dự án rõ ràng)[3].
- **1.2\. Tổng quan về Kiến trúc hướng dịch vụ (SOA - Service-Oriented Architecture)**[1]**:**
  - SOA là gì? Mô hình thiết kế phần mềm trong đó các chức năng được chia nhỏ thành các dịch vụ (services) độc lập[1].
  - Đặc trưng cốt lõi của SOA: Các dịch vụ hoạt động độc lập, không phụ thuộc vào ngôn ngữ của nhau và trao đổi dữ liệu thông qua giao thức chuẩn **HTTP/REST**[1].
- **1.3\. Chuẩn giao tiếp RESTful API:**
  - Định nghĩa API và chuẩn thiết kế RESTful.
  - Các phương thức HTTP (HTTP Methods) cơ bản dùng trong hệ thống: `GET` (Đọc/Truy vấn), `POST` (Tạo mới), `PUT/PATCH` (Cập nhật), `DELETE` (Xóa)[2].

---

### **PHẦN 2: LÝ THUYẾT FRAMEWORK &amp; SO SÁNH (30 điểm Thang điểm)**

**Mục tiêu:** Hoàn thành toàn bộ yêu cầu lý thuyết của đề bài[2].

- **2.1\. Giới thiệu Web Framework đã chọn (Ví dụ: Django / Django REST Framework)**[2]**:**
  - Tổng quan về Django và Django REST Framework (DRF)[4][5].
  - Mô hình kiến trúc của Framework: MVT (Model - View - Template) hoặc MVC (Model - View - Controller)[6].
- **2.2\. Đặc điểm &amp; Đánh giá Ưu / Nhược điểm**[2]**:**
  - **Ưu điểm:** Có sẵn hệ thống ORM mạnh mẽ[7][8], trang quản trị Admin trực quan[8], tích hợp sẵn các tính năng bảo mật và xác thực người dùng[9].
  - **Nhược điểm:** Dung lượng cấu hình ban đầu lớn hơn so với các micro-framework[2].
- **2.3\. So sánh Framework đã chọn với các Framework khác**[2]**:**
  - Bảng so sánh giữa **Django** với các framework Python khác như **FastAPI, Flask, Pyramid, Bottle**[2] dựa trên các tiêu chí: Tốc độ xử lý, độ phức tạp, hệ sinh thái đi kèm và khả năng mở rộng.
- **2.4\. Ứng dụng thực tế (Case study)**[1][2]**:**
  - Ví dụ các hệ thống lớn thực tế đang áp dụng mô hình SOA và REST Web Service để kết nối nhiều dịch vụ độc lập[1][2].

---

### **PHẦN 3: THIẾT KẾ HỆ THỐNG &amp; CƠ SỞ DỮ LIỆU (Mô hình hóa bài toán)**

**Mục tiêu:** Chuyển đổi yêu cầu bài toán quản lý đồ án tốt nghiệp thành sơ đồ thiết kế[1].

- **3.1\. Phân tích Bài toán Quản lý Đồ án Tốt nghiệp cho Sinh viên**[1]**:**
  - Yêu cầu bài toán: Xây dựng hệ thống cho phép quản lý thông tin sinh viên, danh sách đề tài và việc đăng ký đồ án của sinh viên[1].
- **3.2\. Cấu trúc Cơ sở dữ liệu (CSDL) cho trước**[1]**:**
  - Bảng **SINHVIEN**: Lưu thông tin sinh viên (Mã SV, Họ tên, Lớp, Ngành...)[1].
  - Bảng **DETAI**: Lưu thông tin đề tài đồ án (Mã đề tài, Tên đề tài, GV hướng dẫn, Mô tả...)[1].
  - Bảng **DANGKY**: Lưu thông tin đăng ký (Mã đăng ký, Mã SV, Mã đề tài, Ngày đăng ký, Điểm số...)[1].
- **3.3\. Xây dựng Sơ đồ Kiến trúc hệ thống SOA &amp; ERD CSDL**[2]**:**
  - Vẽ sơ đồ ERD thể hiện mối quan hệ giữa các bảng `SINHVIEN`, `DETAI`, `DANGKY`[1].
  - Vẽ sơ đồ kiến trúc SOA thể hiện sự tương tác độc lập giữa Web Client &lt;-&gt; REST API Services &lt;-&gt; Database[1][2].

---

### **PHẦN 4: TRIỂN KHAI DỊCH VỤ WEB SERVICE (30 điểm Thang điểm)**

**Mục tiêu:** Cài đặt dịch vụ Backend, kết nối CSDL và viết các API chức năng[2].

- **4.1\. Thiết lập Môi trường Phát triển (Local Setup)**[4]**:**
  - Tạo môi trường ảo Python (Virtual Environment) và cài đặt Django, Django REST Framework[5][10].
  - Kết nối Framework với Cơ sở dữ liệu (SQLite hoặc PostgreSQL/MySQL)[2][11].
- **4.2\. Xây dựng các Model (ORM)**[1][7]**:**
  - Định nghĩa các lớp Python `SinhVien`, `DeTai`, `DangKy` tương ứng với CSDL[1][7].
  - Thực hiện Migration để tạo bảng trong CSDL[2][12].
- **4.3\. Xây dựng các Web Service / API theo chuẩn RESTful (Chức năng CRUD)**[2]**:**
  - **Dịch vụ Sinh viên (** **SINHVIEN** **):** API lấy danh sách, xem chi tiết, thêm mới, sửa, xóa thông tin sinh viên[2].
  - **Dịch vụ Đề tài (** **DETAI** **):** API CRUD danh sách đề tài đồ án[2].
  - **Dịch vụ Đăng ký (** **DANGKY** **):** API thực hiện cho sinh viên đăng ký đề tài, hủy đăng ký[1][2].
- **4.4\. Xây dựng Logic Nghiệp vụ "Tính điểm"**[2]**:**
  - Cài đặt thuật toán/API chuyên biệt cho chức năng **Tính điểm** (VD: Nhập điểm đồ án, tính điểm trung bình tổng kết, xếp loại hoàn thành đồ án)[2].

---

### **PHẦN 5: TRUY XUẤT DEMO &amp; PHẦN CLIENT (20 điểm Thang điểm)**

**Mục tiêu:** Xây dựng ứng dụng Client để gọi API và minh họa hệ thống chạy thành công[2].

- **5.1\. Xây dựng Ứng dụng Client (Giao diện người dùng)**[2]**:**
  - Tạo giao diện Client đơn giản (Web Client bằng HTML/JS, Bootstrap hoặc công cụ kiểm thử Postman/Swagger/Swagger UI)[2][13].
- **5.2\. Thực hiện Gọi API từ Client tới Web Service**[1][2]**:**
  - Đảm bảo Client gửi yêu cầu HTTP (GET, POST, PUT, DELETE) tới Backend Server và nhận phản hồi dữ liệu dạng JSON[1].
- **5.3\. Kịch bản Chạy thử (Demo) chi tiết**[2]**:**
  - **Bước 1:** Khởi tạo dữ liệu Sinh viên và Đề tài qua API.
  - **Bước 2:** Demo Sinh viên chọn và thực hiện đăng ký Đề tài thành công.
  - **Bước 3:** Gọi API nhập và **Tính điểm** đồ án cho sinh viên[2].
  - **Bước 4:** Truy vấn hiển thị bảng kết quả hoàn chỉnh trên Client[2].

---

### **PHẦN 6: BÁO CÁO, TRÌNH BÀY &amp; SÁNG TẠO (20 điểm Thang điểm)**

**Mục tiêu:** Đạt tối đa điểm số cho phần Báo cáo (15đ) và Bổ sung Sáng tạo (5đ)[2].

- **6.1\. Các Tính năng Sáng tạo &amp; Bổ sung (5 điểm Tối đa)**[2]**:**
  - **Bảo mật (Security):** Tích hợp xác thực API bằng JWT (JSON Web Token) hoặc API Key để bảo vệ các đường dẫn API[2].
  - **Logging:** Ghi log hệ thống (lịch sử truy cập API, nhật ký lỗi)[2].
  - **Tính năng phụ:** Tìm kiếm/Lọc đề tài nâng cao hoặc phân quyền (Giảng viên/Sinh viên).
- **6.2\. Hoàn thiện Báo cáo &amp; Phân công Nhóm (15 điểm Thang điểm)**[2]**:**
  - Đóng gói tài liệu báo cáo đầy đủ các sơ đồ kiến trúc SOA, sơ đồ CSDL ERD, so sánh framework[2].
  - Bảng phân công công việc cụ thể cho từng thành viên trong nhóm (Teamwork)[2].
