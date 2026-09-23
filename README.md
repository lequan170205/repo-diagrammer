# repo-diagrammer

Plugin cho Claude Code: quăng repo vào, yêu cầu vẽ diagram bất kỳ về một tính năng
bất kỳ, và nhận lại hình **có dẫn chứng `file:line` cho từng box và từng mũi tên**,
đã render thử thành công, đã qua một vòng review kiểu tech lead.

Hỗ trợ: C4 Context / Container / Component, sequence, class, ER, state machine,
dataflow, deployment, call graph, use case.

---

## Cài đặt

### Cách 1 — qua plugin marketplace (đầy đủ nhất, có MCP + hook)

Push thư mục này lên GitHub của bạn, rồi trong Claude Code:

```
/plugin marketplace add <user>/<repo>
/plugin install repo-diagrammer@repo-diagrammer-marketplace
```

### Cách 2 — chạy local không cần push

```bash
claude --plugin-dir /đường/dẫn/tới/repo-diagrammer
```

### Cách 3 — copy thẳng vào config (chắc ăn nhất)

```bash
bash install.sh              # cài cho user: ~/.claude
bash install.sh ./my-project # cài cho riêng 1 project
```

Cách 3 bỏ qua hệ thống plugin nên **không kèm MCP và hook** — nếu muốn MCP validator,
thêm tay:

```bash
claude mcp add mermaid-validator -- npx -y @rtuin/mcp-mermaid-validator@latest
```

### Bắt buộc làm một lần sau khi cài

```bash
npm i -g @mermaid-js/mermaid-cli
npx puppeteer browsers install chrome-headless-shell
```

Bước thứ hai hay bị quên. Thiếu nó, mermaid-cli báo lỗi trông y hệt lỗi cú pháp.
Plugin có bắt riêng trường hợp này và báo đúng bản chất, nhưng cài trước vẫn hơn.

Rồi chạy `/diagram-doctor` — nó nói cho bạn còn thiếu gì, và chỉ gợi ý những thứ
thực sự liên quan tới ngôn ngữ trong repo của bạn.

---

## Dùng

Nói chuyện bình thường, skill tự kích hoạt:

```
vẽ sequence diagram cho luồng checkout
vẽ class diagram của module payments
vẽ ERD từ migrations
module notification hoạt động thế nào? vẽ giúp tôi
vẽ use case diagram cho hệ thống này
vẽ sơ đồ kiến trúc tổng thể
```

Hoặc dùng slash command khi muốn ép chạy đủ quy trình:

| Lệnh | Việc |
|---|---|
| `/diagram <loại + tính năng>` | Vẽ một diagram, đủ 7 bước |
| `/diagram-set <phạm vi>` | Bộ diagram mạch lạc cho onboarding / review kiến trúc |
| `/diagram-review <file>` | Soi diagram có sẵn ngược lại với code |
| `/diagram-doctor` | Kiểm tra và sửa tooling |

Nói thêm **đối tượng đọc** sẽ ra kết quả tốt hơn hẳn — diagram cho onboarding giấu
bớt nhánh lỗi, diagram để debug sự cố thì ngược lại.

---

## Kết quả nhận được

File `docs/diagrams/<slug>.md` gồm: diagram đã validate, mục "How to read it",
**bảng Evidence** (từng phần tử ↔ `file:line` hoặc `tool:<lệnh>`), mục **Gaps &
assumptions**, và mục rủi ro kiến trúc đáng xem tiếp. Kèm `<slug>.spec.yaml` để lần
sau regenerate từ spec và diff được.

Nếu có dòng nào trong Evidence sai, báo lại — agent sửa spec rồi vẽ lại, không vá đè.

---

## Vì sao nó chính xác hơn việc hỏi thẳng

Bốn chốt chặn, xếp theo mức độ quan trọng:

**1. Ưu tiên trích xuất tĩnh hơn là đọc.** Agent chạy pyreverse, madge,
dependency-cruiser, `go list`, jdeps, `pg_dump`, `prisma schema` trước khi tự đọc
code. Parser không bịa quan hệ; LLM nhớ mang máng thì có. Lệnh đã chạy được ghi vào
bảng Evidence dưới dạng `tool:<lệnh>` để bạn chạy lại kiểm chứng.

**2. Bắt buộc viết spec trước khi vẽ.** Mỗi node/edge phải có evidence mới được lên
hình; không có thì xuống mục Gaps. Đây là chốt chặn chính chống hallucination —
những cái "Cache", "Load Balancer", "Auth Service" nghe hợp lý mà không tồn tại
trong code.

**3. Chốt chặn render.** `validate_mermaid.sh` render thật từng block, in ra block
lỗi kèm số dòng và nguyên nhân khả dĩ. Có hook `PostToolUse` tự chạy mỗi lần ghi file
`.md` chứa Mermaid — diagram sai cú pháp không thoát ra được tới bạn.

**4. Subagent review.** `diagram-reviewer` mở lại từng `file:line` được trích dẫn và
đối chiếu với hình, trong context riêng. Nó tìm: phần tử bịa, phần tử bị bỏ sót, mũi
tên ngược chiều, cạnh async vẽ thành sync, sai cardinality ERD, trộn mức trừu tượng.

Cộng thêm: `repo-scout` chạy song song trên repo lớn để không đốt context chính, và
`references/layout-quality.md` áp ba nguyên tắc graph drawing — thứ tự khai báo quyết
định layout, số đường cắt nhau là yếu tố dự báo mạnh nhất về độ khó hiểu, và proximity
thắng màu sắc.

---

## Giới hạn, nói thẳng

- **Use case diagram là suy luận, không phải trích xuất.** Actor suy từ role/permission,
  use case suy từ route và job. Code không biết ý đồ nghiệp vụ. Plugin ghi rõ điều này
  vào Gaps mỗi lần vẽ.
- **Call graph tĩnh sót interface, DI và reflection.** Đặc biệt nặng với Go interface,
  Spring DI, và event bus. Agent sẽ nói rõ chỗ nào nó mất dấu thay vì đoán.
- **Sequence diagram không có tool nào trích được** — phải đọc code. Đây là loại
  diagram cần bạn kiểm tra bảng Evidence kỹ nhất.
- **PlantUML không render trên GitHub.** Mặc định dùng Mermaid; chọn PlantUML chỉ khi
  bạn cần notation C4 thật hoặc use case UML kiểu sách giáo khoa.

---

## Cấu trúc

```
repo-diagrammer/
├── .claude-plugin/{plugin,marketplace}.json
├── .mcp.json                        mermaid-validator MCP
├── commands/                        /diagram, /diagram-set, /diagram-review, /diagram-doctor
├── agents/                          repo-scout, diagram-reviewer
├── hooks/                           tự validate Mermaid khi ghi file
├── install.sh                       cài kiểu copy thẳng
└── skills/repo-diagram/
    ├── SKILL.md                     quy trình 7 bước + 5 rule bất di bất dịch
    ├── references/
    │   ├── diagram-types.md         chọn loại, rule từng loại, anti-pattern
    │   ├── extraction.md            công thức static analysis theo ngôn ngữ
    │   ├── notation.md              cú pháp, bẫy parser, template C4 + use case
    │   └── layout-quality.md        nguyên tắc làm hình dễ đọc
    ├── assets/spec.template.yaml    bước trung gian chống bịa
    └── scripts/
        ├── repo_map.sh              recon toàn repo
        ├── feature_trace.sh         tên tính năng → anchor trong code
        ├── extract_structure.sh     trích xuất tĩnh (classes/deps/routes/schema)
        ├── validate_mermaid.sh      render thử, chẩn đoán lỗi
        └── check_deps.sh            kiểm tra tooling
```

MIT.
