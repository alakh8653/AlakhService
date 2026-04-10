class PricingEngineError(Exception):
    pass

class CouponNotFoundError(PricingEngineError):
    def __init__(self, msg="Coupon not found"):
        super().__init__(msg)

class CouponExpiredError(PricingEngineError):
    def __init__(self, msg="Coupon has expired or is not active"):
        super().__init__(msg)

class CouponExhaustedError(PricingEngineError):
    def __init__(self, msg="Coupon has reached maximum uses"):
        super().__init__(msg)
