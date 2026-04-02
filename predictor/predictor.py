from river import compose
from river import linear_model
from river import preprocessing
from river import optim

class StreamPredictor:
    """
    Maintains the state for a single WAN link's predictive model.
    Handles the temporal offset between predicting t+1 and learning from t.
    """
    def __init__(self, learning_rate=0.01):
        # Inside predictor.py's __init__ method:
        self.model = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LinearRegression(
                optimizer=optim.Adam(lr=0.05), # Upgraded from SGD to Adam
                intercept_lr=0.05
            )
        )
        
        # State tracker to align features at t with the target observed at t+1
        self.previous_features = None

    def process_telemetry(self, current_features: dict, actual_target: float = None) -> float:
        """
        Executes one complete streaming ML step: Learn (from past) -> Predict (for future).
        
        Args:
            current_features (dict): Telemetry at time t (e.g., {'latency': 10, 'rx': 500})
            actual_target (float): The actual metric observed right now (the ground truth for t-1)
            
        Returns:
            float: The predicted value for the target metric at t+1
        """
        
        # 1. LEARN: If we have features from the previous step and the new ground truth, update weights
        if self.previous_features is not None and actual_target is not None:
            self.model.learn_one(self.previous_features, actual_target)
            
        # 2. PREDICT: Guess the future state based on current telemetry
        prediction = self.model.predict_one(current_features)
        
        # 3. STORE: Save the current features so we can learn against them in the next API call
        self.previous_features = current_features
        
        return prediction
