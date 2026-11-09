# 📋 HƯỚNG DẪN KIỂM THỬ HỆ THỐNG VỚI SWAGGER UI

### Cách mở nhanh Swagger UI cục bộ:
```powershell
python -m http.server 8080 --directory swagger
```
> Sau khi chạy lệnh trên, mở trình duyệt truy cập: [http://localhost:8080](http://localhost:8080)  
> *(Hoặc truy cập trực tiếp qua API Gateway nếu đã deploy: [http://localhost:8000/swagger/](http://localhost:8000/swagger/))*

---

# 🚀 KỊCH BẢN DEMO 1: LUỒNG NGHIỆP VỤ CHÍNH
khởi động dự án: .\start_all.ps1
mở web dự án : http://localhost:5173/
> **URL Swagger UI:** [http://localhost:8000/docs/](http://localhost:8000/docs/)  
> **Tài khoản test:**
> - **Admin:** `admin` / `admin` (Role 1)
> - **Giảng viên:** `Gv0001` / `123456` (Role 2)
> - **Sinh viên:** `4651050118` / `4651050118` (Role 3)

---

### BƯỚC 1: Admin đăng nhập, tạo khoa/ngành, sinh viên, giảng viên

#### 1.1. Đăng nhập Admin
* **API:** `POST /auth/login/`
* **Body:**
  ```json
  {
    "identifier": "admin",
    "password": "admin"
  }
  ```
* **Kết quả:** `200 OK` ➔ Copy chuỗi `access` ➔ Bấm nút **Authorize 🔓** trên cùng, dán token vào và bấm **Authorize**.

#### 1.2. Tạo Khoa (Department)
* **API:** `POST /academic/api/departments/`
* **Body:**
  ```json
  {
    "department_id": "CNTT",
    "name": "Khoa Cong nghe thong tin"
  }
  ```
* **Kết quả:** `201 Created` *(Nếu đã có trong DB thì trả về `400` duplicate, ta chỉ cần gọi `GET /academic/api/departments/` để xem lại)*.

#### 1.3. Tạo Ngành (Major)
* **API:** `POST /academic/api/majors/`
* **Body:**
  ```json
  {
    "major_id": "105",
    "name": "Cong nghe thong tin",
    "department_id": "CNTT"
  }
  ```
* **Kết quả:** `201 Created` *(hoặc `GET /academic/api/majors/` xem danh sách)*.

#### 1.4. Tạo Sinh viên
* **API:** `POST /academic/api/students/`
* **Body:**
  ```json
  {
    "student_id": "4651050118",
    "major_id": "105",
    "accumulated_credits": 120,
    "gpa": 3.2
  }
  ```
* **Kết quả:** `201 Created` *(hoặc gọi `GET /academic/api/students/4651050118/` để xem chi tiết sinh viên đã có sẵn)*.

#### 1.5. Tạo Giảng viên
* **API:** `POST /academic/api/lecturers/` (hoặc gọi `GET /academic/api/lecturers/` để xem giảng viên `GV0001`).
* **Body:**
  ```json
  {
    "lecturer_id": "GV0001",
    "department_id": "CNTT",
    "academic_title": "Thac si"
  }
  ```
* **Kết quả:** `201 Created` hoặc `200 OK`.

---

### BƯỚC 2: Giảng viên tạo đề tài (Trạng thái chờ duyệt: status = 0)

#### 2.1. Đăng nhập Giảng viên
* **API:** `POST /auth/login/`
* **Body:**
  ```json
  {
    "identifier": "GV0001",
    "password": "lecture"
  }
  ```
* **Kết quả:** `200 OK` ➔ Copy `access` token ➔ Bấm **Authorize 🔓** (bấm Logout token cũ, dán token mới vào ➔ Authorize).

#### 2.2. Tạo Đề tài mới
* **API:** `POST /topics/api/v1/topics/`
* **Body:**
  ```json
  {
    "topic_id": "DT001",
    "name": "Xay dung he thong quan ly do an theo kien truc SOA su dung django",
    "major_id": "105",
    "advisor_id": "GV0001",
    "description": "Nghien cuu microservices va API Gateway",
    "req_GPA": 2.5,
    "studentQuota": 2,
    "status": 0
  }
  ```
  *(Chú ý các cột mới đồng bộ với UI:
  - `req_GPA: 2.5`: Điểm GPA tối thiểu yêu cầu (từ 0.0 đến 4.0).
  - `studentQuota: 2`: Chỉ tiêu số lượng sinh viên tối đa được phép đăng ký.
  - `status: 0`: Trạng thái Chờ duyệt; với vai trò Giảng viên hệ thống tự động gán status 0 và advisor_id chính là giảng viên)*.
* **Kết quả:** `201 Created` ➔ Đề tài đã tạo thành công và đang ở trạng thái Chờ duyệt (chưa mở cho sinh viên đăng ký).

---

### BƯỚC 3: Admin duyệt và chuyển đề tài sang trạng thái 2 (Mở đăng ký)

#### 3.1. Đăng nhập lại Admin
* **API:** `POST /auth/login/` (`admin` / `admin`) ➔ Lấy token Admin gắn lại vào **Authorize 🔓**.

#### 3.2. Duyệt đề tài (Đổi status sang 2 - Mở đăng ký)
* **API:** `PATCH /topics/api/v1/topics/DT001/` *(hoặc `PUT /topics/api/v1/topics/DT001/`)*
* **Body (khuyên dùng PATCH):**
  ```json
  {
    "status": 2
  }
  ```
  *(Nếu sử dụng phương thức `PUT`, cần truyền đầy đủ toàn bộ các trường để đảm bảo validation:*
  ```json
  {
    "topic_id": "DT001",
    "name": "Xay dung he thong quan ly do an theo kien truc SOA su dung django",
    "major_id": "105",
    "advisor_id": "GV0001",
    "description": "Nghien cuu microservices va API Gateway",
    "req_GPA": 2.5,
    "studentQuota": 2,
    "status": 2
  }
  ```
  *)*  
  *(Chú ý: `status: 1` là Đã duyệt, `status: 2` là Đã duyệt & Mở đăng ký cho sinh viên)*.
* **Kết quả:** `200 OK` ➔ Đề tài `DT001` chính thức mở cho sinh viên.

---

### BƯỚC 4: Sinh viên xem đề tài mở và đăng ký

#### 4.1. Đăng nhập Sinh viên
* **API:** `POST /auth/login/`
* **Body:**
  ```json
  {
    "identifier": "4651050118",
    "password": "4651050118"
  }
  ```
* **Kết quả:** `200 OK` ➔ Copy token Sinh viên gắn vào nút **Authorize 🔓**.

#### 4.2. Xem danh sách đề tài mở phù hợp với Khoa
* **API:** `GET /registrations/api/v1/available-topics/`
* **Thao tác:** Bấm **Try it out** ➔ **Execute**.
* **Kết quả:** `200 OK` ➔ Thấy đề tài `DT001` trong danh sách `results` kèm thông tin GPA yêu cầu và chỉ tiêu:
  ```json
  {
    "topic_id": "DT001",
    "name": "Xay dung he thong quan ly do an theo kien truc SOA su dung django",
    "major_id": "105",
    "status": 2,
    "req_GPA": 2.5,
    "studentQuota": 2,
    "registered_count": 0,
    "eligible": true,
    "ineligibility_reason": null
  }
  ```
  *(Sinh viên có GPA 3.2 $\ge$ GPA yêu cầu 2.5 và chỉ tiêu còn trống nên `eligible = true`)*.

#### 4.3. Sinh viên đăng ký đề tài
* **API:** `POST /registrations/api/v1/registrations/`
* **Body:**
  ```json
  {
    "topic_id": "DT001",
    "semester": "2026-1"
  }
  ```
* **Kết quả:** `201 Created` kèm `registration_id` (ví dụ: `c4b14d8e-1736-4d1a-9694-8ab36fba7c18`) và `status: 1` (Active).  
  👉 *Copy lại mã `registration_id` này để dùng cho Bước 5.*

---

### BƯỚC 5: Giảng viên xem danh sách đăng ký và hủy một đăng ký

#### 5.1. Đăng nhập Giảng viên
* **API:** `POST /auth/login/` (`GV0001` / `lecture`) ➔ Lấy token gắn vào **Authorize 🔓**.

#### 5.2. Giảng viên xem danh sách sinh viên đã đăng ký đề tài `DT001`
* **API:** `GET /registrations/api/v1/topics/DT001/registrations/`
* **Thao tác:** Nhập `topic_id: DT001` ➔ Bấm **Execute**.
* **Kết quả:** `200 OK` ➔ Thấy sinh viên `4651050118` đã đăng ký đề tài `DT001` trong mảng `results`.

#### 5.3. Hủy lượt đăng ký của sinh viên (Thực hiện bởi Admin hoặc Sinh viên)
* *Lưu ý về phân quyền trong hệ thống:* Endpoint hủy đăng ký quản trị yêu cầu quyền Admin (`role: 1`), còn Giảng viên (`role: 2`) có quyền xem danh sách và chấm điểm (`PUT .../point/`). Sinh viên (`role: 3`) có thể tự hủy lượt đăng ký của mình qua `DELETE /registrations/api/v1/registrations/{id}/`.
* **Thao tác Admin hủy đăng ký:**
  1. Đăng nhập lại Admin (`admin` / `admin`) và gắn token Admin vào **Authorize 🔓**.
  2. Gọi **API:** `DELETE /registrations/api/v1/topics/DT001/registrations/{registration_id}/`
  3. Tham số:
     - `topic_id`: `DT001`
     - `registration_id`: Dán mã `registration_id` đã copy ở Bước 4.3.
     - Bấm **Execute**.
* **Kết quả:** `204 No Content` ➔ Hủy đăng ký thành công, bảo toàn lịch sử.

---

### BƯỚC 6: Consul UI (4 service passing) & Demo chịu lỗi (503)

#### 6.1. Kiểm tra Service Discovery trên Consul UI
* Mở trình duyệt truy cập: **[http://localhost:8500](http://localhost:8500)**
* Thấy cả 4 services (`auth-service`, `academic-service`, `regist-service`, `topic-service`) đều có dấu tích xanh **Passing**.
* *Giải thích ngắn:* Gateway sử dụng Consul để tự động tìm kiếm instance khỏe mạnh mà không cần hard-code IP.

#### 6.2. Demo tính chịu lỗi (Fault Tolerance)
* Vào cửa sổ terminal của **Registration Service (:8003)**, bấm `Ctrl + C` để tắt service.
* Quay lại Swagger UI, gọi lại một API của registration (ví dụ `GET /registrations/api/v1/available-topics/`).
* **Kết quả:** Gateway trả về ngay mã **`503 Service Unavailable`** (Dịch vụ tạm thời không khả dụng, không làm sập Gateway hay ảnh hưởng tới các service khác).

