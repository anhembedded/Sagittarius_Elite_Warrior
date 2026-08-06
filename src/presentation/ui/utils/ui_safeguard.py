from functools import wraps
import traceback

def safe_ui_action(func):
    """
    Decorator for PySide6 Slots in Presenters.
    Catches exceptions to prevent silent UI hangs, logs the error,
    and forces the FSM (if present) into an ERROR or IDLE state to unlock the UI.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            error_msg = f"❌ [UI Error] {func.__name__} failed: {str(e)}"
            
            # 1. Log the error to the UI if possible
            if hasattr(self, 'ui_log_signal'):
                self.ui_log_signal.emit(error_msg)
            else:
                print(error_msg)
                traceback.print_exc()
                
            # 2. Recovery Mechanism: Force FSM to a safe state to unlock UI
            if hasattr(self, 'fsm') and hasattr(self.fsm, 'transition_to'):
                # We attempt to transition to ERROR state if it exists, otherwise IDLE.
                # Since we don't have direct access to the enum here, we try by string name 
                # or fallback to unlocking logic if the state enum is provided.
                try:
                    # In case the FSM requires an enum, we check its available states.
                    # This is a generic approach since the specific Enum might differ.
                    safe_state = None
                    if hasattr(self, 'DashboardState'):
                        safe_state = getattr(self.DashboardState, 'ERROR', None) or getattr(self.DashboardState, 'IDLE', None)
                    
                    if safe_state:
                        self.fsm.transition_to(safe_state)
                    else:
                        # Attempt string-based or fallback state if Enum is not explicitly registered on self
                        self.ui_log_signal.emit("Attempting to force UI unlock...")
                        # If no strict enum is found, we can't easily guess it.
                        # We leave this open for the presenter to handle via a dedicated unlock method if FSM fails.
                except Exception as recovery_error:
                    print(f"Failed to recover FSM state: {recovery_error}")
                    
            # 3. Fallback: If no FSM but we need to unlock UI components
            if hasattr(self, 'fsm'):
                from Binace_Bot.src.presentation.ui.constants import UIMode
                from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError
                try:
                    self.fsm.transition_to(UIMode.ERROR)
                except InvalidStateTransitionError:
                    pass
                try:
                    self.fsm.transition_to(UIMode.IDLE)
                except InvalidStateTransitionError:
                    pass
            elif hasattr(self, 'view') and hasattr(self.view, 'control_card'):
                if hasattr(self.view.control_card, 'apply_ui_mode'):
                    from Binace_Bot.src.presentation.ui.constants import UIMode
                    self.view.control_card.apply_ui_mode(UIMode.IDLE)

    return wrapper
