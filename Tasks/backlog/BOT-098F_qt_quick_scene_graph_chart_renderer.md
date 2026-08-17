# BOT-098F — Qt Quick Scene Graph retained chart renderer

**Parent:** `BOT-098`
**Depends on:** `BOT-098F1`, `BOT-098F2`, `BOT-098F2A` ✅
**Ưu tiên:** P1
**Độ phức tạp:** L / Performance-specialized
**Trạng thái:** Backlog

## Quyết định kiến trúc

Không dùng TradingView Lightweight Charts, WebEngine hoặc JavaScript bridge.
Không tiếp tục micro-optimize PyQtGraph sau khi native gate xác nhận CPU
`QGraphicsView` repaint vẫn vượt frame budget ở viewport mặc định.

Chart Backtest sẽ chuyển sang custom Qt Quick Scene Graph item để cùng một
rendering stack với QML shell. Renderer giữ GPU geometry theo layer và chỉ cập
nhật buffer khi data revision, viewport hoặc LOD thay đổi.

## Thiết kế chuẩn

1. Renderer core là C++ `QQuickItem`/`QSGGeometryNode`; không override
   `updatePaintNode()` bằng Python vì GIL/render-thread callback sẽ tái tạo một
   bottleneck khác. Python tiếp tục sở hữu business logic và data preparation.
2. `QQuickItem.updatePaintNode()` sở hữu cây retained-mode; không tạo
   object/pen/brush theo từng frame.
3. Immutable, contiguous render snapshot đi từ Python/UI thread vào pending
   native buffer; render thread atomic-swap theo revision. `QSGNode` không được
   chạm từ Python worker hoặc presenter.
4. Các layer độc lập: candle wick/body, volume, indicator polyline,
   marker/trade và crosshair. Dirty flag cập nhật đúng layer, không rebuild toàn
   scene khi chuột di chuyển.
5. Dùng OHLC/volume power-of-two LOD từ `BOT-098E`; indicator dùng min/max
   envelope theo pixel column để giữ peak/trough; trade marker không được gộp
   mất semantic.
6. Pan/zoom biến đổi camera/transform trước; geometry chỉ rebucket khi vượt LOD
   boundary hoặc cache margin.
7. Text/axis/tooltip tách khỏi bulk geometry; cache glyph/layout và chỉ đổi khi
   label payload thực sự thay đổi.
8. Backend đi theo Qt RHI (D3D11/Vulkan/OpenGL tùy Qt), không hard-code GPU API.

## Migration slices

- F1: hạ tầng CMake/QML native plugin (`BOT-098F1`).
- F2: retained read-only candle geometry (`BOT-098F2`) ✅.
- F2A: fractional camera, visible auto-Y và raw UTC/price axis tick contract
  (`BOT-098F2A`) ✅.
- F3: volume + indicator buffers và semantic equivalence tests.
- F4: marker/crosshair/tooltip + dev FPS.
- F5: thay chart Backtest, giữ fallback PyQtGraph một release rồi loại bỏ khi
  sanity/E2E ổn định.

## Acceptance criteria

- Một end-to-end performance gate duy nhất trên profile chuẩn; không lặp lại
  micro A/B không dẫn tới quyết định kiến trúc.
- Frame pacing gần 60 FPS khi pan/zoom; final viewport không có frame spike thấy
  rõ ở 6.420+ nến, 5 indicators và 1.000+ marker.
- Pixel/semantic tests bảo toàn OHLC extreme, volume sum, indicator peak/trough,
  marker identity và final crosshair candle.
- Không còn `QGraphicsView`/PyQtGraph trong chart Backtest sau migration cuối;
  không tạo thêm nested offscreen composition với `QQuickWidget`.
