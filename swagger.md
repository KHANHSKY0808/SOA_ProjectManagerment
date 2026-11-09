openapi: 3.0.3
info:
  title: Hệ Thống Quản Lý Đồ Án Tốt Nghiệp - Kiến Trúc SOA
  description: |
    Tài liệu OpenAPI và giao diện kiểm thử Swagger UI tập trung cho toàn bộ hệ thống SOA.
    Mọi yêu cầu được định tuyến qua **API Gateway** (`http://localhost:8000`).
    
    ### Phân quyền các Role trong hệ thống:
    - `role = 1`: Quản trị viên (Admin) / Phòng đào tạo
    - `role = 2`: Giảng viên (Lecturer)
    - `role = 3`: Sinh viên (Student)
  version: 1.0.0
servers:
  - url: http://localhost:8000
    description: API Gateway (Port 8000)

tags:
  - name: 1. Auth Service (:8001)
    description: Xác thực danh tính, đăng nhập, phát hành và làm mới JWT Token
  - name: 2. Academic Service (:8002)
    description: Quản lý Khoa, Ngành, Chuyên ngành, Giảng viên và Sinh viên
  - name: 3. Topic Service (:8004)
    description: Quản lý danh sách Đề tài tốt nghiệp và trạng thái phê duyệt
  - name: 4. Registration Service (:8003)
    description: Nghiệp vụ đăng ký, hủy đăng ký đề tài và kiểm tra điều kiện sinh viên

paths:
  # ==========================================
  # AUTH SERVICE
  # ==========================================
  /auth/login/:
    post:
      tags:
        - 1. Auth Service (:8001)
      summary: Đăng nhập hệ thống để nhận JWT Token
      description: Nhận `identifier` (hoặc email/userid) cùng mật khẩu để cấp cặp `access` và `refresh` JWT token.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - identifier
                - password
              properties:
                identifier:
                  type: string
                  example: "4651050118"
                  description: "Email hoặc User ID (VD: 'admin' hoặc '4651050118')"
                password:
                  type: string
                  example: "4651050118"
                  description: Mật khẩu người dùng
      responses:
        "200":
          description: Đăng nhập thành công, trả về JWT Access Token
          content:
            application/json:
              schema:
                type: object
                properties:
                  access:
                    type: string
                    description: JWT Access Token (dùng gắn vào Header Bearer)
                  refresh:
                    type: string
                    description: JWT Refresh Token
        "400":
          description: Thiếu thông tin đăng nhập hoặc dữ liệu không hợp lệ
        "401":
          description: Sai tên đăng nhập hoặc mật khẩu

  /auth/token/refresh/:
    post:
      tags:
        - 1. Auth Service (:8001)
      summary: Làm mới Access Token bằng Refresh Token
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - refresh
              properties:
                refresh:
                  type: string
      responses:
        "200":
          description: Cấp Access Token mới thành công
        "401":
          description: Refresh Token không hợp lệ hoặc đã hết hạn

  /auth/me/:
    get:
      tags:
        - 1. Auth Service (:8001)
      summary: Lấy thông tin tài khoản hiện tại
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Thông tin tài khoản người dùng đang đăng nhập
          content:
            application/json:
              schema:
                type: object
                properties:
                  user_id:
                    type: string
                    example: "SV001"
                  email:
                    type: string
                    example: "sv001@example.com"
                  role:
                    type: integer
                    example: 3
                    description: "1: Admin, 2: Giảng viên, 3: Sinh viên"
        "401":
          description: Chưa truyền hoặc Token không hợp lệ

  # ==========================================
  # ACADEMIC SERVICE
  # ==========================================
  /academic/api/departments/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Lấy danh sách các Khoa (Departments / Faculties)
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách các khoa

  /academic/api/majors/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Lấy danh sách các Ngành học (Majors)
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách các ngành học

  /academic/api/sub-majors/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Lấy danh sách Chuyên ngành (Sub-majors)
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách các chuyên ngành

  /academic/api/students/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Lấy danh sách Sinh viên
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách sinh viên
    post:
      tags:
        - 2. Academic Service (:8002)
      summary: Thêm mới hồ sơ Sinh viên (Yêu cầu role 1)
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - student_id
                - major_id
              properties:
                student_id:
                  type: string
                  example: "SV999"
                major_id:
                  type: string
                  example: "1"
                sub_major_id:
                  type: string
                  nullable: true
                  example: null
                accumulated_credits:
                  type: integer
                  example: 120
                gpa:
                  type: number
                  example: 3.5
      responses:
        "201":
          description: Tạo sinh viên thành công
        "403":
          description: Không đủ quyền (Cần Role 1)

  /academic/api/students/{id}/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Xem chi tiết hồ sơ một Sinh viên
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
          example: "SV001"
      responses:
        "200":
          description: Chi tiết sinh viên
        "404":
          description: Không tìm thấy sinh viên

  /academic/api/lecturers/:
    get:
      tags:
        - 2. Academic Service (:8002)
      summary: Lấy danh sách Giảng viên
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách giảng viên

  # ==========================================
  # TOPIC SERVICE
  # ==========================================
  /topics/api/v1/topics/:
    get:
      tags:
        - 3. Topic Service (:8004)
      summary: Lấy danh sách tất cả Đề tài
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách đề tài đồ án
    post:
      tags:
        - 3. Topic Service (:8004)
      summary: Tạo mới Đề tài đồ án (Yêu cầu role 1 hoặc 2)
      description: |
        Tạo mới một đề tài:
        - Giảng viên (`role: 2`): Trạng thái đề tài tự động đặt là `status: 0` (Chờ duyệt) và người hướng dẫn gắn với tài khoản đang đăng nhập.
        - Quản trị viên (`role: 1`): Có thể chỉ định trạng thái ban đầu (`status: 1` hoặc `2`).
        - Các trường yêu cầu mới trên UI: `req_GPA` (GPA tối thiểu yêu cầu từ 0.0 - 4.0) và `studentQuota` (chỉ tiêu sinh viên tối đa >= 1).
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - topic_id
                - name
                - major_id
              properties:
                topic_id:
                  type: string
                  example: "DT001"
                  description: Mã đề tài
                name:
                  type: string
                  example: "Xây dựng hệ thống quản lý đồ án theo kiến trúc SOA"
                  description: Tên đề tài đồ án
                req_GPA:
                  type: number
                  minimum: 0
                  maximum: 4
                  example: 2.5
                  description: Điểm GPA tích lũy tối thiểu yêu cầu (từ 0.0 đến 4.0)
                studentQuota:
                  type: integer
                  minimum: 1
                  maximum: 2147483647
                  example: 2
                  description: Chỉ tiêu số lượng sinh viên tối đa được phép đăng ký đề tài
                major_id:
                  type: string
                  example: "105"
                  description: Mã ngành học phụ trách đề tài
                advisor_id:
                  type: string
                  nullable: true
                  example: "GV0001"
                  description: Mã giảng viên hướng dẫn (với role 2 tự động gán theo token)
                description:
                  type: string
                  example: "Nghiên cứu microservices và API Gateway"
                  description: Nội dung mô tả chi tiết đề tài
                status:
                  type: integer
                  description: "Trạng thái: 0: Chờ duyệt, 1: Đã duyệt, 2: Mở đăng ký, 3: Đóng đăng ký"
                  example: 0
      responses:
        "201":
          description: Tạo đề tài thành công
        "400":
          description: Dữ liệu không hợp lệ hoặc thiếu trường bắt buộc
        "403":
          description: Không đủ quyền (Cần Role 1 hoặc Role 2)

  /topics/api/v1/topics/{id}/:
    get:
      tags:
        - 3. Topic Service (:8004)
      summary: Xem chi tiết một Đề tài
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
      responses:
        "200":
          description: Thông tin chi tiết đề tài
        "404":
          description: Không tìm thấy đề tài
    put:
      tags:
        - 3. Topic Service (:8004)
      summary: Cập nhật toàn bộ Đề tài (Yêu cầu role 1 Admin)
      description: Cập nhật toàn bộ thông tin đề tài. Chỉ Admin (Role 1) mới có quyền chỉnh sửa.
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - topic_id
                - name
                - major_id
              properties:
                topic_id:
                  type: string
                  example: "DT001"
                name:
                  type: string
                  example: "Xây dựng hệ thống quản lý đồ án theo kiến trúc SOA"
                major_id:
                  type: string
                  example: "105"
                advisor_id:
                  type: string
                  nullable: true
                  example: "GV0001"
                req_GPA:
                  type: number
                  minimum: 0
                  maximum: 4
                  example: 2.5
                  description: Điểm GPA tích lũy tối thiểu yêu cầu (0.0 - 4.0)
                studentQuota:
                  type: integer
                  minimum: 1
                  maximum: 2147483647
                  example: 2
                  description: Chỉ tiêu số lượng sinh viên tối đa
                description:
                  type: string
                  example: "Nghiên cứu microservices và API Gateway"
                status:
                  type: integer
                  description: "0: Chờ duyệt, 1: Đã duyệt, 2: Mở đăng ký, 3: Đóng đăng ký"
                  example: 2
      responses:
        "200":
          description: Cập nhật thành công
        "400":
          description: Dữ liệu không hợp lệ
        "403":
          description: Không đủ quyền (Cần Role 1 Admin)
    patch:
      tags:
        - 3. Topic Service (:8004)
      summary: Cập nhật một phần Đề tài (Yêu cầu role 1 Admin)
      description: Dùng để duyệt đề tài (đổi status sang 1 hoặc 2), đóng đăng ký (status sang 3) hoặc sửa từng trường riêng biệt.
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: integer
                  description: "Đổi trạng thái đề tài: 1 (Đã duyệt), 2 (Mở đăng ký), 3 (Đóng đăng ký)"
                  example: 2
                req_GPA:
                  type: number
                  minimum: 0
                  maximum: 4
                  example: 2.5
                studentQuota:
                  type: integer
                  minimum: 1
                  maximum: 2147483647
                  example: 2
                name:
                  type: string
                description:
                  type: string
                major_id:
                  type: string
                advisor_id:
                  type: string
      responses:
        "200":
          description: Cập nhật thành công
        "403":
          description: Không đủ quyền (Cần Role 1 Admin)
    delete:
      tags:
        - 3. Topic Service (:8004)
      summary: Xóa Đề tài (Yêu cầu role 1 Admin)
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "204":
          description: Xóa thành công (Body rỗng)
        "403":
          description: Không đủ quyền (Cần Role 1 Admin)

  # ==========================================
  # REGISTRATION SERVICE
  # ==========================================
  /registrations/api/v1/available-topics/:
    get:
      tags:
        - 4. Registration Service (:8003)
      summary: Lấy danh sách đề tài mở phù hợp với Khoa của Sinh viên
      description: |
        Endpoint chỉ dành cho Sinh viên (`role: 3`). 
        Service tự động trích xuất `student_id` từ JWT Token, liên hệ Academic-Service để lấy Khoa của sinh viên và lọc ra các đề tài đang ở trạng thái `status: 2` (Open).
        Mỗi đề tài trả về đầy đủ các trường GPA yêu cầu, chỉ tiêu, số lượng đã đăng ký và cờ đánh giá đủ điều kiện.
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Danh sách đề tài sinh viên được phép đăng ký
          content:
            application/json:
              schema:
                type: object
                properties:
                  results:
                    type: array
                    items:
                      type: object
                      properties:
                        topic_id:
                          type: string
                          example: "DT001"
                        name:
                          type: string
                          example: "Xây dựng hệ thống quản lý đồ án theo kiến trúc SOA"
                        major_id:
                          type: string
                          example: "105"
                        status:
                          type: integer
                          example: 2
                        req_GPA:
                          type: number
                          example: 2.5
                          description: GPA tối thiểu yêu cầu của đề tài
                        studentQuota:
                          type: integer
                          example: 2
                          description: Chỉ tiêu tối đa sinh viên
                        registered_count:
                          type: integer
                          example: 0
                          description: Số lượng sinh viên đã đăng ký
                        eligible:
                          type: boolean
                          example: true
                          description: Sinh viên hiện tại có đủ điều kiện đăng ký không
                        ineligibility_reason:
                          type: string
                          nullable: true
                          example: null
                          description: Lý do không đủ điều kiện nếu eligible = false
                  next_after:
                    type: string
                    nullable: true
        "401":
          description: Thiếu hoặc sai Token
        "403":
          description: Tài khoản không phải vai trò Sinh viên (Role 3)

  /registrations/api/v1/registrations/:
    get:
      tags:
        - 4. Registration Service (:8003)
      summary: Xem lịch sử / trạng thái đăng ký của chính Sinh viên hiện tại
      description: Trả về danh sách các đề tài sinh viên đã đăng ký (mới nhất lên đầu).
      security:
        - bearerAuth: []
      parameters:
        - name: status
          in: query
          required: false
          description: Lọc theo trạng thái ('active' hoặc 'cancelled')
          schema:
            type: string
            enum: [active, cancelled]
      responses:
        "200":
          description: Lịch sử đăng ký của sinh viên
    post:
      tags:
        - 4. Registration Service (:8003)
      summary: Sinh viên đăng ký Đề tài đồ án
      description: |
        Đăng ký một đề tài tốt nghiệp:
        - Sinh viên chỉ được có tối đa 1 đề tài hiện thời (`status: 1`).
        - Đề tài phải đang ở trạng thái mở (`status: 2`).
        - Khoa của sinh viên và khoa của đề tài phải trùng khớp.
        - Điểm GPA của sinh viên phải thỏa mãn GPA yêu cầu của đề tài và đề tài chưa vượt quá chỉ tiêu.
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - topic_id
              properties:
                topic_id:
                  type: string
                  example: "DT001"
                  description: Mã đề tài muốn đăng ký
                semester:
                  type: string
                  example: "2026-1"
                  description: Học kỳ đăng ký
      responses:
        "201":
          description: Đăng ký thành công bản ghi mới
          content:
            application/json:
              schema:
                type: object
                properties:
                  registration_id:
                    type: string
                    example: "c4b14d8e-1736-4d1a-9694-8ab36fba7c18"
                  topic_id:
                    type: string
                    example: "DT001"
                  semester:
                    type: string
                    example: "2026-1"
                  status:
                    type: integer
                    example: 1
                    description: "1: Đang hoạt động, 0: Đã hủy"
        "200":
          description: Đã đăng ký đề tài này từ trước (Idempotent response)
        "400":
          description: Đề tài chưa mở hoặc không cùng khoa hoặc không đủ điều kiện GPA / hết chỉ tiêu
        "409":
          description: Sinh viên đã có đăng ký đề tài khác đang hoạt động

  /registrations/api/v1/registrations/{id}/:
    delete:
      tags:
        - 4. Registration Service (:8003)
      summary: Sinh viên tự hủy đăng ký đề tài
      description: "Đổi trạng thái lượt đăng ký của chính mình thành đã hủy (status: 0), bảo toàn lịch sử."
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          description: Mã registration_id
          schema:
            type: string
      responses:
        "204":
          description: Hủy đăng ký thành công (Body rỗng)

  /registrations/api/v1/topics/{topic_id}/registrations/:
    get:
      tags:
        - 4. Registration Service (:8003)
      summary: Giảng viên / Admin xem danh sách sinh viên đăng ký đề tài (Role 1 hoặc 2)
      description: |
        Xem danh sách sinh viên đã đăng ký đề tài:
        - Quản trị viên (`role: 1`): Xem danh sách đăng ký của bất kỳ đề tài nào.
        - Giảng viên (`role: 2`): Chỉ được xem danh sách đăng ký của các đề tài do chính mình phụ trách (`advisor_id` khớp với user_id).
      security:
        - bearerAuth: []
      parameters:
        - name: topic_id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
        - name: after
          in: query
          required: false
          schema:
            type: string
          description: Con trỏ phân trang (registration_id cuối của trang trước)
      responses:
        "200":
          description: Danh sách sinh viên đăng ký đề tài
          content:
            application/json:
              schema:
                type: object
                properties:
                  results:
                    type: array
                    items:
                      type: object
                      properties:
                        registration_id:
                          type: string
                          example: "c4b14d8e-1736-4d1a-9694-8ab36fba7c18"
                        student_id:
                          type: string
                          example: "4651050118"
                        student_name:
                          type: string
                          nullable: true
                          example: "Nguyen Van A"
                        semester:
                          type: string
                          example: "2026-1"
                        status:
                          type: integer
                          example: 1
                          description: "1: Hoạt động, 0: Đã hủy"
                        point:
                          type: string
                          nullable: true
                          example: "8.50"
                          description: Điểm đánh giá nếu đã chấm
                        created_at:
                          type: string
                          example: "2026-10-26T07:00:00Z"
                  next_after:
                    type: string
                    nullable: true
                  names_unavailable:
                    type: boolean
                    example: false
        "403":
          description: Yêu cầu quyền Giảng viên phụ trách đề tài hoặc Admin

  /registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/point/:
    put:
      tags:
        - 4. Registration Service (:8003)
      summary: Chấm điểm đồ án cho sinh viên (Yêu cầu role 1 hoặc 2)
      description: |
        Nhập điểm tốt nghiệp cho sinh viên đăng ký đề tài:
        - Yêu cầu đề tài đã đóng đăng ký (`status: 3`).
        - Điểm từ `0.00` đến `10.00` với tối đa 2 chữ số thập phân.
        - Giảng viên (`role: 2`) chỉ được chấm điểm đề tài mình hướng dẫn. Quản trị viên (`role: 1`) có thể chấm điểm mọi đề tài.
      security:
        - bearerAuth: []
      parameters:
        - name: topic_id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
        - name: registration_id
          in: path
          required: true
          schema:
            type: string
          example: "c4b14d8e-1736-4d1a-9694-8ab36fba7c18"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - point
              properties:
                point:
                  type: string
                  example: "8.50"
                  description: Điểm số từ 0.00 đến 10.00 (VD: "8.50")
      responses:
        "200":
          description: Chấm điểm thành công
          content:
            application/json:
              schema:
                type: object
                properties:
                  registration_id:
                    type: string
                    example: "c4b14d8e-1736-4d1a-9694-8ab36fba7c18"
                  topic_id:
                    type: string
                    example: "DT001"
                  point:
                    type: string
                    example: "8.50"
                  updated_at:
                    type: string
                    example: "2026-10-26T08:00:00Z"
        "400":
          description: Điểm số không hợp lệ
        "403":
          description: Không đủ quyền (Không phải giảng viên hướng dẫn của đề tài)
        "409":
          description: Đề tài chưa đóng đăng ký (status khác 3) hoặc lượt đăng ký đã bị hủy

  /registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/:
    delete:
      tags:
        - 4. Registration Service (:8003)
      summary: Admin hủy 1 lượt đăng ký của sinh viên (Yêu cầu role 1 Admin)
      description: |
        Hủy lượt đăng ký của sinh viên từ phía quản trị viên.
        Đổi trạng thái lượt đăng ký thành đã hủy (`status: 0`), bảo toàn lịch sử đăng ký.
        Chỉ Admin (`role: 1`) có quyền thực hiện.
      security:
        - bearerAuth: []
      parameters:
        - name: topic_id
          in: path
          required: true
          schema:
            type: string
          example: "DT001"
        - name: registration_id
          in: path
          required: true
          schema:
            type: string
          example: "c4b14d8e-1736-4d1a-9694-8ab36fba7c18"
      responses:
        "204":
          description: Hủy đăng ký thành công (Body rỗng)
        "403":
          description: Không đủ quyền (Chỉ Admin Role 1 mới được hủy đăng ký ở endpoint này)

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: "Nhập JWT Access Token thu được từ endpoint `POST /auth/login/` (không cần gõ chữ 'Bearer ')"

<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SOA Project - Swagger UI API Explorer</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      padding: 0;
      background: #f8fafc;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .custom-header {
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      color: white;
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .custom-header h1 {
      margin: 0;
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .badge {
      background: #3b82f6;
      color: white;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .header-links {
      display: flex;
      gap: 1rem;
      align-items: center;
      font-size: 0.875rem;
    }
    .header-link {
      color: #94a3b8;
      text-decoration: none;
      transition: color 0.15s ease;
    }
    .header-link:hover {
      color: white;
    }
    #swagger-ui {
      max-width: 1400px;
      margin: 0 auto;
      padding: 1rem 1.5rem 3rem;
    }
    /* Polish default Swagger UI container */
    .swagger-ui .topbar {
      display: none;
    }
    .swagger-ui .info {
      margin: 20px 0 30px;
    }
    .swagger-ui .info .title {
      font-family: 'Inter', sans-serif;
      font-weight: 700;
      color: #0f172a;
    }
    .swagger-ui .btn.authorize {
      border-color: #2563eb;
      color: #2563eb;
      border-radius: 6px;
      font-weight: 600;
      transition: all 0.2s;
    }
    .swagger-ui .btn.authorize svg {
      fill: #2563eb;
    }
    .swagger-ui .btn.authorize:hover {
      background: #eff6ff;
    }
    .swagger-ui .opblock {
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      border: 1px solid rgba(0,0,0,0.08);
      margin-bottom: 12px;
    }
    .swagger-ui .opblock .opblock-summary {
      padding: 8px 16px;
    }
  </style>
</head>
<body>
  <header class="custom-header">
    <h1>
      <span>🎓 SOA Graduation Project</span>
      <span class="badge">Swagger UI Client</span>
    </h1>
    <div class="header-links">
      <span>API Gateway: <strong>http://localhost:8000</strong></span>
      <a href="./openapi.yaml" target="_blank" class="header-link">📄 Tải OpenAPI Spec</a>
    </div>
  </header>

  <div id="swagger-ui"></div>

  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      // Determine URL to openapi.yaml
      const specUrl = window.location.pathname.startsWith('/docs') ? '/openapi.yaml' : './openapi.yaml';
      
      const ui = SwaggerUIBundle({
        url: specUrl,
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "BaseLayout",
        defaultModelsExpandDepth: -1,
        docExpansion: "list",
        filter: true,
        tryItOutEnabled: true,
        persistAuthorization: true
      });
      window.ui = ui;
    };
  </script>
</body>
</html>

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
