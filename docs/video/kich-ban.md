# Kịch bản video giải thích đồ án theo rubric

Video: `docs/video/giai-thich-do-an-theo-rubric.mp4` (16:9, lời đọc tiếng Việt, không phụ đề). Mỗi trang ứng với một tiêu chí trong phiếu chấm; đọc lời dưới đây để ôn trước khi bảo vệ.

> Lời đọc viết phiên âm cho máy đọc (ví dụ *ây pi ai* = API, *ô tê pê* = OTP, *sa ga* = saga, *rét* = REST, *pốt grét* = PostgreSQL, *đốc cơ com pốt* = Docker Compose, *meo hốc* = MailHog, *dê gơ* = Jaeger).

## 01 · Mở đầu

- Bấm một nút để đóng học phí. Nghe thì đơn giản.
- Nhưng hệ thống phải trừ tiền đúng một lần, gạch nợ đúng một lần, và gửi biên lai về email.
- Còn nếu hai người cùng bấm, đúng cùng một giây, thì sao?
- Video này giải thích đồ án iBanking đóng học phí của nhóm mười một, đi lần lượt qua tám tiêu chí chấm điểm.

## 02 · Phiếu chấm

- Phiếu chấm có tám tiêu chí, tổng mười điểm. Nặng nhất là phần chức năng thanh toán: hai điểm.
- Nhưng hãy nhớ năm cái trần điểm. Không chạy được: tối đa bốn. Chỉ là một khối nguyên khối: sáu rưỡi. Không có ô tê pê: bảy. Không xử lý đồng thời: bảy rưỡi. Thiếu sơ đồ kiến trúc: tám.
- Đồ án này vượt qua cả năm. Các trang sau chỉ ra bằng chứng cho từng ý.

## 03 · Một vòng như người dùng

- Trước khi vào kỹ thuật, hãy đi một vòng như người dùng.
- Anh Minh đăng nhập, gõ mã số sinh viên năm hai hai hát không không không một. Hệ thống tự hiện tên sinh viên và học phí: chín triệu rưỡi.
- Anh đồng ý điều khoản, bấm xác nhận, rồi nhập mã sáu số vừa nhận qua email.
- Số dư giảm từ năm mươi triệu xuống bốn mươi triệu năm trăm nghìn. Học phí chuyển sang đã đóng, lịch sử có thêm một dòng, và biên lai về hộp thư.

## 04 · Tiêu chí 1 · Use case

- Tiêu chí một: phân tích nghiệp vụ. Sơ đồ ca sử dụng trả lời hai câu: ai dùng hệ thống, và dùng để làm gì.
- Có ba tác nhân: người dùng iBanking, hệ thống email để gửi mã và biên lai, và hệ thống đào tạo cung cấp sinh viên cùng học phí.
- Người dùng có bảy chức năng, từ đăng nhập tới xem lịch sử. Ba chức năng còn lại được gọi kèm bên trong, như gửi mã qua email hay kiểm tra số dư.
- Không có chức năng đăng ký, vì đề bài không yêu cầu. Biết bỏ đúng chỗ cũng là một điểm cộng.

## 05 · Tiêu chí 1 · ERD

- Nửa sau của tiêu chí một là sơ đồ quan hệ thực thể: bản thiết kế các bảng dữ liệu.
- Có chín bảng, chia cho sáu cơ sở dữ liệu, mỗi dịch vụ giữ phần của mình.
- Mỗi bảng có khóa chính, cột cần thiết và quan hệ rõ ràng. Một sinh viên có nhiều khoản học phí. Một tài khoản có nhiều dòng sổ cái.
- Giữa hai dịch vụ khác nhau chỉ có liên kết logic qua mã định danh, không có khóa ngoại xuyên cơ sở dữ liệu. Đó là chủ ý của kiến trúc.

## 06 · Tiêu chí 2 · Sơ đồ kiến trúc

- Tiêu chí hai, một điểm rưỡi: kiến trúc mai crô xơ vít. Hãy hình dung một ngân hàng có nhiều quầy, mỗi quầy làm đúng một việc và giữ sổ riêng.
- Khách không vào thẳng quầy. Mọi yêu cầu đi qua cổng ây pi ai, như quầy lễ tân: kiểm tra vé đăng nhập, rồi chỉ tới đúng quầy.
- Phía sau là sáu quầy: xác thực, tài khoản, học phí, thanh toán, mã ô tê pê, và thông báo. Mỗi quầy là một chương trình riêng, một con tê nơ riêng, một cơ sở dữ liệu riêng.
- Quầy thanh toán là người điều phối, gọi bốn quầy kia qua rét. Quầy thông báo là cửa duy nhất ra dịch vụ email bên ngoài.

## 07 · Tiêu chí 2 · Vì sao thiết kế vậy

- Phân rã tốt là mỗi dịch vụ chỉ có một lý do để thay đổi. Quầy tài khoản không biết học phí là gì. Quầy học phí không biết tiền từ đâu ra.
- Vì sao gọi nhau bằng rét đồng bộ? Vì người dùng đang đứng chờ kết quả, nên cần biết thành công hay lỗi ngay lập tức.
- Vì sao mỗi dịch vụ một cơ sở dữ liệu? Để không ai đọc lén sổ của ai. Muốn dữ liệu, phải hỏi qua ây pi ai.
- Và vì sao có một người điều phối? Để luôn có một nơi trả lời được: giao dịch này đang ở bước nào, hỏng vì sao.

## 08 · Tiêu chí 3 · REST API

- Tiêu chí ba: thiết kế rét ây pi ai. Mỗi ây pi ai là một địa chỉ cộng với một động từ.
- Động từ ghét để đọc, như tra cứu học phí theo mã số sinh viên. Động từ pốt để tạo hoặc thực hiện, như tạo giao dịch hay xác nhận mã.
- Đồ án có mười một ây pi ai nghiệp vụ, ba ây pi ai kiểm tra hệ thống, và mười bốn ây pi ai nội bộ chỉ cho các dịch vụ gọi nhau. Tài liệu xoa gơ được sinh tự động.

## 09 · Tiêu chí 3 · Phản hồi và lỗi

- Nửa sau của tiêu chí ba là cách hệ thống trả lời: mẫu dữ liệu vào, mẫu dữ liệu ra, và mã trạng thái.
- Hai trăm là thành công. Hai trăm lẻ một: đã tạo giao dịch. Bốn trăm lẻ một: chưa đăng nhập. Bốn trăm lẻ bốn: không có mã số sinh viên này. Bốn trăm lẻ chín: xung đột, như không đủ số dư, hay học phí đã được đóng.
- Mọi lỗi trả về cùng một khuôn: mã lỗi, lời nhắn, chi tiết và mã theo dõi. Lỗi từ dịch vụ bên trong được giữ nguyên mã khi chuyển ra ngoài, nên giao diện báo đúng lỗi.
- Dữ liệu được kiểm tra ở bốn tầng: kiểu dữ liệu, quy tắc nghiệp vụ, quyền sở hữu, và ràng buộc trong cơ sở dữ liệu.

## 10 · Tiêu chí 4 · Database

- Tiêu chí bốn: cơ sở dữ liệu. Hệ thống dùng pốt grét, sáu cơ sở dữ liệu cho sáu dịch vụ, khớp đúng sơ đồ thực thể.
- Điểm mạnh nằm ở các ràng buộc. Số dư không bao giờ âm. Mỗi giao dịch chỉ ghi sổ một lần. Mỗi khoản học phí chỉ có một giao dịch thành công. Kể cả code có sai, cơ sở dữ liệu vẫn chặn lại.
- Dữ liệu mẫu có bốn người dùng và năm sinh viên, trong đó một khoản đã đóng sẵn để thử trường hợp bị chặn. Dữ liệu nằm trên ổ đĩa của đốc cơ, khởi động lại vẫn còn.

## 11 · Tiêu chí 5 · Khởi tạo giao dịch

- Tiêu chí năm, nặng nhất, hai điểm: chức năng và luồng thanh toán. Đăng nhập kiểm tra mật khẩu đã băm, rồi cấp một vé điện tử có hạn một giờ.
- Khi tạo giao dịch, dịch vụ thanh toán hỏi quầy học phí và quầy tài khoản, rồi kiểm tra ba điều: khoản học phí tồn tại, chưa được đóng, và số dư đủ.
- Yêu cầu tạo giao dịch không hề có ô số tiền. Số tiền luôn lấy từ khoản nợ, nên không ai trả một phần hay sửa số tiền được.
- Mỗi giao dịch đi qua các trạng thái: chờ mã, đang xử lý, rồi thành công hoặc thất bại.

## 12 · Tiêu chí 5 · OTP

- Mã ô tê pê có năm luật.
- Gắn với đúng một giao dịch. Không trùng với mã đang hiệu lực của giao dịch khác. Hết hạn sau năm phút. Chỉ dùng thành công một lần. Và nhập sai năm lần thì bị khóa.
- Mã được băm trước khi lưu, nên người xem được cơ sở dữ liệu cũng không đọc ra. Bấm gửi lại mã thì mã cũ bị thu hồi ngay.
- Mã đi qua dịch vụ thông báo tới email. Khi demo, mở hộp thư meo hốc để lấy mã.

## 13 · Tiêu chí 5 · Thanh toán thành công

- Khi mã đúng, dịch vụ thanh toán chạy một chuỗi bước, gọi là sa ga.
- Trừ tiền và ghi sổ cái trong cùng một giao dịch. Gạch nợ học phí. Đánh dấu thành công. Gửi email biên lai. Mỗi bước được ghi vào nhật ký, xem được ngay trên giao diện.
- Vì sao trừ tiền trước, gạch nợ sau? Vì tiền có thể hoàn lại an toàn. Còn học phí thì không nên nhấp nháy từ đã đóng về chưa đóng trước mắt sinh viên.

## 14 · Tiêu chí 6 · Nhất quán

- Tiêu chí sáu, một điểm rưỡi: giao dịch và đồng thời. Câu hỏi khó nhất thường nằm ở đây.
- Mỗi dịch vụ một cơ sở dữ liệu, nên không gói tất cả vào một giao dịch duy nhất được. Nhóm dùng hai tầng: trong một dịch vụ là giao dịch a xít; xuyên dịch vụ là sa ga có bù trừ.
- Trừ tiền xong mà gạch nợ thất bại, hệ thống chạy bước ngược: hoàn đúng số tiền, với mã tham chiếu riêng, nên gọi lại bao nhiêu lần cũng chỉ hoàn một lần.
- Còn nếu máy sập giữa chừng, tác vụ đối soát chạy mỗi ba mươi giây sẽ tìm giao dịch treo quá sáu mươi giây, và đưa nó về kết quả đúng.

## 15 · Tiêu chí 6 · Cùng một tài khoản

- Tình huống đồng thời thứ nhất: hai giao dịch dùng chung một tài khoản, mà số dư chỉ đủ cho một.
- Nếu cả hai cùng đọc số dư rồi cùng trừ, tiền bị tiêu hai lần. Hệ thống chặn bằng khóa dòng: giao dịch đến trước khóa dòng tài khoản lại, giao dịch sau phải xếp hàng chờ.
- Tới lượt, giao dịch sau đọc số dư mới nhất, thấy không đủ, và bị từ chối. Kết quả trong bài kiểm thử: một thành công, một thất bại, số dư cuối bằng không.
- Phía sau còn hai lớp chặn: mã tham chiếu duy nhất, và ràng buộc số dư không âm.

## 16 · Tiêu chí 6 · Cùng một học phí

- Tình huống thứ hai: anh Minh và chị Hà cùng đóng học phí cho một sinh viên, cùng một lúc.
- Cả hai đều bị trừ tiền. Nhưng ở quầy học phí, khóa dòng chỉ cho một người đổi trạng thái từ chưa đóng sang đã đóng. Người tới sau nhận lỗi: học phí đã được thanh toán.
- Sa ga lập tức hoàn tiền cho người tới sau. Giao diện hiện rõ chuỗi: trừ tiền, gạch nợ thất bại, hoàn tiền. Lịch sử số dư có một dòng trừ và một dòng cộng lại đúng số tiền.
- Chốt chặn cuối: chỉ mục duy nhất trong cơ sở dữ liệu bảo đảm mỗi khoản học phí chỉ có một giao dịch thành công.

## 17 · Tiêu chí 7 · Giao diện

- Tiêu chí bảy: giao diện. Ứng dụng web viết thuần, không dùng thư viện khung, và gọi thật vào ây pi ai qua cổng chung.
- Một màn hình đi trọn luồng: đăng nhập, tra cứu học phí, thanh toán, nhập mã, xem kết quả và lịch sử.
- Nút xác nhận giao dịch chỉ bật khi đã tra cứu, còn học phí phải đóng, đủ số dư, và đã đồng ý điều khoản.

## 18 · Tiêu chí 8 · Triển khai và kiểm thử

- Tiêu chí tám: tài liệu, triển khai và demo. Rít mi hướng dẫn cài đặt, cấu hình, khởi chạy, kèm năm tài liệu phân tích thiết kế.
- Chỉ một lệnh đốc cơ com pốt là dựng đủ mười một con tê nơ, khởi động đúng thứ tự nhờ kiểm tra sức khỏe.
- Bộ kiểm thử tự động có iu nít, tích hợp, đầu cuối và đồng thời. Lượt chạy ngày mười bốn tháng chín: tám mươi tám ca đạt, một ca bỏ qua vì phải chờ đủ năm phút. Ca đó chạy riêng với hạn tám giây cũng đạt.

## 19 · Điểm cộng mức 9–10

- Muốn chạm mức chín, mười điểm, phiếu chấm nhắc tới: cổng ây pi ai, tính lũy đẳng, kiểm thử đồng thời và đầu cuối, ghi log và truy vết. Đồ án có đủ.
- Lũy đẳng nghĩa là bấm xác nhận ba lần cùng lúc vẫn chỉ trừ tiền một lần.
- Truy vết với dê gơ cho thấy một lần tạo giao dịch đi qua sáu dịch vụ, cùng một mã theo dõi, kèm thời gian từng bước.

## 20 · Demo và bảo vệ

- Khi demo, đi theo thứ tự: kiến trúc và mười một con tê nơ, luồng thành công, thanh toán hộ người khác, các luật ô tê pê, rồi hai tình huống đồng thời. Phần đồng thời ăn điểm nhất, hãy dành nhiều thời gian nhất.
- Bị hỏi: đây có thật là mai crô xơ vít không? Hãy tắt dịch vụ học phí: chỉ phần học phí báo lỗi năm trăm lẻ ba, đăng nhập và xem số dư vẫn chạy.
- Bị hỏi: vì sao không dùng một giao dịch chung? Trả lời: mỗi dịch vụ một cơ sở dữ liệu, nên dùng sa ga, bước sau hỏng thì bù trừ bước trước.
- Và chủ động nói giới hạn: nhất quán cuối cùng chứ không tức thì; một máy chủ pốt grét chứa sáu cơ sở dữ liệu để tiết kiệm tài nguyên. Biết rõ giới hạn của mình, đó là cách nói của dân chuyên.

## 21 · Tổng kết

- Tóm lại: sáu dịch vụ, một cổng, sáu cơ sở dữ liệu, mã ô tê pê qua email, và hai tình huống đồng thời đều được xử lý và kiểm thử.
- Đồ án môn Kiến trúc hướng dịch vụ, nhóm mười một. Chúc cả nhóm bảo vệ thật tự tin.
