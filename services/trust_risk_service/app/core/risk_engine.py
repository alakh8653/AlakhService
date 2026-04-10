class BayesianRiskScorer:
    """
    Bayesian risk scoring using Beta distribution.
    prior_alpha, prior_beta represent prior belief about risk.
    EMA for recency weighting of behavioral signals.
    """
    
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 9.0, ema_decay: float = 0.1):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.ema_decay = ema_decay
    
    def compute_score(self, risk_events: int, safe_events: int, ema_score: float = 0.0) -> float:
        """
        Posterior mean of Beta(alpha + risk_events, beta + safe_events).
        score = alpha / (alpha + beta), range [0, 1].
        Blended with EMA for temporal smoothing.
        """
        alpha = self.prior_alpha + risk_events
        beta = self.prior_beta + safe_events
        bayesian_score = alpha / (alpha + beta)
        return (1 - self.ema_decay) * bayesian_score + self.ema_decay * ema_score
    
    def update_ema(self, current_ema: float, new_signal: float) -> float:
        """Update EMA: ema_new = decay * new_signal + (1 - decay) * ema_old"""
        return self.ema_decay * new_signal + (1 - self.ema_decay) * current_ema
    
    def risk_level(self, score: float) -> str:
        if score < 0.2: return "LOW"
        if score < 0.5: return "MEDIUM"
        if score < 0.75: return "HIGH"
        return "CRITICAL"

risk_scorer = BayesianRiskScorer()
