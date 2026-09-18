# Design đề xuất — Strategy Properties input lifecycle

> Mục tiêu: tách rõ **chỉnh sửa nháp**, **lưu cấu hình**, và **lưu + chạy lại**.
> Đây là design proposal; chưa phải hành vi đã implement.

## 1. Component boundary

```mermaid
flowchart LR
    User([User])

    subgraph View[Presentation — StrategyPropertiesDialog]
        Fields[Input controls\nQLineEdit / SpinBox / ComboBox / Checkbox]
        Draft[DraftFormState\nraw values + dirty fields]
        Actions[Actions\nDiscard · Save · Save & Run]
    end

    subgraph Application[Application / Presenter boundary]
        DraftCmd[CommitStrategyPropertiesDraft]
        SaveCmd[SaveStrategyProperties]
        RunCmd[SaveAndRunBacktest]
        Result[Validation result\nfield errors + saved snapshot]
    end

    subgraph Domain[Domain / configuration]
        Validator[Strategy + broker validator]
        Config[Backtest configuration state]
        Runner[Backtest runner / FSM]
    end

    User --> Fields
    Fields <--> Draft
    Draft --> Actions
    Actions --> DraftCmd
    Actions --> SaveCmd
    Actions --> RunCmd
    DraftCmd --> Validator
    SaveCmd --> Validator
    RunCmd --> Validator
    Validator --> Result
    Result --> Draft
    SaveCmd --> Config
    RunCmd --> Config --> Runner
```

### Ownership

| Thành phần | Chịu trách nhiệm | Không làm |
| :--- | :--- | :--- |
| Dialog | giữ draft, focus, field error, nút thao tác | tự chạy Backtest hoặc tự đổi domain state |
| Presenter | route command, điều phối result/FSM | đọc widget trực tiếp |
| Coordinator/use case | parse, validate, apply snapshot atomically | biết focus/dialog widget |
| Domain config | invariant strategy/broker | biết UI action nào khởi phát |

## 2. Ba command riêng biệt

```mermaid
flowchart TD
    Event{User event}

    Event -->|type / focus loss| Draft[Update local DraftFormState]
    Event -->|Save| Save[SaveStrategyProperties]
    Event -->|Save & Run| SaveRun[SaveAndRunBacktest]
    Event -->|Cancel| Discard[DiscardDraft]

    Draft -->|optional debounce validation| Inline[Show inline validation]
    Save --> Validate{Valid?}
    SaveRun --> ValidateRun{Valid?}

    Validate -->|No| Errors[Keep dialog open\nshow field errors]
    Validate -->|Yes| Persist[Persist atomically\nmark config dirty]
    Persist --> KeepOpen[Keep dialog open\nshow Saved status]

    ValidateRun -->|No| Errors
    ValidateRun -->|Yes| PersistRun[Persist atomically]
    PersistRun --> Close[Close dialog]
    Close --> Run[Dispatch Backtest run]

    Discard --> Restore[Restore last persisted snapshot]
    Restore --> CloseDiscard[Close dialog]
```

**Khuyến nghị chính:** `focus loss` chỉ cập nhật **draft** (và có thể validate),
không persist, không close, không run. Điều này làm nút **Hủy** có ý nghĩa rõ
ràng: bỏ toàn bộ thay đổi chưa Save.

## 3. Sequence — chỉnh field rồi chuyển focus

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant F as Input field
    participant D as Dialog DraftFormState
    participant V as Validator

    U->>F: type "42"
    F->>D: update(field, rawValue)
    U->>F: focus another control
    F->>D: editingFinished(field)
    D->>V: validateField(field, rawValue) [optional]
    V-->>D: valid | field error
    D-->>U: field remains editable, dialog stays open
    Note over D: No persistence<br/>No botParamsSaved<br/>No Backtest run
```

## 4. Sequence — Save & Run thành công

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant D as Dialog
    participant P as Presenter
    participant C as Configuration use case
    participant S as Config store / screen state
    participant F as Backtest FSM

    U->>D: click Save & Run
    D->>P: SaveAndRunBacktest(draft snapshot)
    P->>C: validateAndPersist(snapshot)
    C->>C: validate strategy + broker invariants
    alt validation fails
        C-->>P: ValidationErrors(by field)
        P-->>D: render errors
        Note over D: Dialog remains open
    else validation succeeds
        C->>S: persist complete snapshot atomically
        C-->>P: Saved(snapshot version)
        P->>D: close after saved acknowledgement
        P->>F: dispatch RUN_REQUESTED(snapshot version)
    end
```

## 5. Dialog state machine

```mermaid
stateDiagram-v2
    [*] --> Opening
    Opening --> Editing: hydrate persisted snapshot into draft

    Editing --> Editing: field change / focus loss\nupdate draft + optional field validation
    Editing --> Invalid: Save or Save & Run + invalid draft
    Invalid --> Editing: user changes draft

    Editing --> Saving: Save + valid draft
    Saving --> Editing: persisted + show saved feedback

    Editing --> SavingAndRunning: Save & Run + valid draft
    SavingAndRunning --> Closed: persisted + run accepted

    Editing --> Discarding: Cancel
    Invalid --> Discarding: Cancel
    Discarding --> Closed: discard draft
    Closed --> [*]
```

## 6. Data contract

```mermaid
classDiagram
    class StrategyPropertiesDraft {
        +Map strategyInputs
        +BrokerProperties brokerProperties
        +Set dirtyFields
        +Map fieldErrors
        +int baseVersion
    }

    class PersistedStrategyProperties {
        +Map strategyInputs
        +BrokerProperties brokerProperties
        +int version
    }

    class ValidationResult {
        +bool valid
        +Map fieldErrors
        +PersistedStrategyProperties normalizedSnapshot
    }

    StrategyPropertiesDraft --> ValidationResult : validate
    ValidationResult --> PersistedStrategyProperties : valid
```

## 7. Acceptance criteria cho design mới

- Chuyển focus A → B không đóng dialog và không chạy Backtest.
- Enter chỉ thực hiện nghĩa được chốt rõ trong UX (khuyến nghị: validate/commit
  draft, không run).
- **Cancel** không đổi persisted configuration nếu chưa Save.
- **Save** persist toàn bộ snapshot atomically, dialog vẫn mở.
- **Save & Run** chỉ chạy sau khi snapshot đã validate và persist thành công.
- Validation lỗi giữ toàn bộ draft người dùng đã nhập; không reset sang default.
- Dynamic strategy field và static broker field theo cùng lifecycle.
- Tests chứng minh riêng các hành vi: focus loss, Enter, Cancel, Save, Save &
  Run, validation error, và snapshot consistency.
