# System Architecture & Event-Driven Flows

This document contains Mermaid diagrams illustrating the Clean Architecture, CQRS, and Event-Driven flows within the Binance Bot.

## 1. CQRS & Event-Driven Architecture (Flowchart)

This diagram shows the high-level boundaries between layers and how Commands, Queries, and Events travel through the system.

```mermaid
flowchart TD
    %% Presentation Layer
    subgraph Presentation ["1. Presentation Layer"]
        CLI["CLI / Interactive Shell"]
    end

    %% Application Layer - CQRS
    subgraph AppLayer ["2. Application Layer (CQRS)"]
        Dispatcher["App Dispatcher (app.dispatch)"]
        
        subgraph Commands ["Commands (Write/Action)"]
            StartStream["StartLiveStreamCommand"]
            StopStream["StopLiveStreamCommand"]
            RunBacktest["RunBacktestCommand"]
            StopBacktest["StopBacktestCommand"]
        end
        
        subgraph Queries ["Queries (Read)"]
            GetKlines["GetHistoricalKlinesQuery"]
        end
        
        subgraph EventHandlers ["Event Handlers"]
            TickHandler["MarketTickEventHandler"]
            CandleClosedHandler["CandleClosedEventHandler"]
        end
    end

    %% Engine & Core
    subgraph Engine ["Sagittarius Engine"]
        EventBus["EventBus (IEventBus)"]
    end

    %% Domain Layer
    subgraph Domain ["3. Domain Layer"]
        Aggregator["CandleAggregator (Business Rules)"]
        Entities["MarketData (Entities)"]
    end

    %% Infrastructure Layer
    subgraph Infrastructure ["4. Infrastructure Layer"]
        BinanceWS["BinanceWebsocketService"]
        SQLiteRepo["SQLAlchemyMarketDataRepository"]
    end

    %% Luồng điều khiển (Control Flow)
    CLI --> Dispatcher
    Dispatcher --> Commands
    Dispatcher --> Queries

    Queries -.-> |"Tối ưu limit & order_by_desc"| SQLiteRepo
    Commands -.-> |"Bật/Tắt Socket"| BinanceWS
    Commands -.-> |"Cờ báo (BacktestState)"| RunBacktest

    %% Luồng sự kiện (Event Flow)
    BinanceWS == "1. emit(MarketTickEvent)" ==> EventBus
    RunBacktest == "1. emit(Mock MarketTickEvent)" ==> EventBus
    
    EventBus == "2. Route" ==> TickHandler
    TickHandler --> |"3. Cập nhật"| Aggregator
    Aggregator --> Entities
    
    Aggregator -.-> |"4. Nếu nến đóng, sinh ra"| ClosedEvent["CandleClosedEvent"]
    ClosedEvent ==> EventBus
    EventBus ==> CandleClosedHandler
    CandleClosedHandler --> |"5. Lưu vào DB"| SQLiteRepo
```

## 2. Real-Time Tick Processing Flow (Sequence Diagram)

This sequence diagram details the exact step-by-step flow of handling a Live Tick, from WebSocket reception to UI updates and DB persistence.

```mermaid
sequenceDiagram
    autonumber
    
    actor Exchange as Binance API
    participant WS as BinanceWebsocketService (Infra)
    participant EB as EventBus (Engine)
    participant Handler as MarketTickEventHandler (App)
    participant Agg as CandleAggregator (Domain)
    participant Repo as SQLAlchemyMarketDataRepository (Infra)

    Exchange->>WS: Nhận luồng K-line stream (1s)
    WS->>EB: emit(MarketTickEvent)
    EB->>Handler: invoke handle(event)
    
    Handler->>Agg: Đưa tick vào Aggregator xử lý logic
    
    alt Nến chưa đóng (Intermediate Tick)
        Agg-->>Handler: Trả về trạng thái nến hiện tại (đang chạy)
    else Nến đã đóng (Candle Closed)
        Agg-->>Handler: Xác nhận nến đã hoàn thiện (Is_Closed = True)
        
        Handler->>EB: emit(CandleClosedEvent)
        EB->>Repo: CandleClosedEventHandler gọi save_klines()
        Repo-->>EB: Đã lưu SQLite (WAL mode)
    end
```
