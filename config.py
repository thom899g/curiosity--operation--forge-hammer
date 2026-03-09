"""
Centralized configuration management for Curiosity Trading System.
Environment variables are loaded with validation and type safety.
"""
import os
from typing import Optional
from pydantic import BaseSettings, Field, validator
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('curiosity_trading.log')
    ]
)
logger = logging.getLogger(__name__)

class TradingConfig(BaseSettings):
    """Pydantic configuration with environment variable validation"""
    
    # Web3 Configuration
    BASE_RPC_URL: str = Field(
        default="https://mainnet.base.org",
        description="Base L2 RPC endpoint"
    )
    PRIVATE_KEY: str = Field(
        default="",
        description="Wallet private key (keep secure!)"
    )
    WALLET_ADDRESS: str = Field(
        default="",
        description="Trading wallet address"
    )
    
    # Exchange Configuration
    CCXT_EXCHANGE: str = Field(
        default="binance",
        description="Exchange for price data"
    )
    
    # Firebase Configuration
    FIREBASE_CREDENTIALS_PATH: str = Field(
        default="firebase-credentials.json",
        description="Path to Firebase service account JSON"
    )
    
    # API Keys (with validation)
    QUICKNODE_API_KEY: Optional[str] = None
    INFURA_API_KEY: Optional[str] = None
    
    # Trading Parameters
    INITIAL_CAPITAL: float = Field(
        default=13.34,
        ge=0.0,
        description="Initial capital in USD"
    )
    TARGET_CAPITAL: float = Field(
        default=100.0,
        gt=0.0,
        description="Target capital in USD"
    )
    MAX_POSITION_PERCENT: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description="Maximum position size as percentage of capital"
    )
    
    # Risk Management
    MAX_DAILY_LOSS_PERCENT: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Maximum daily loss percentage"
    )
    GAS_PRICE_MULTIPLIER: float = Field(
        default=1.3,
        gt=1.0,
        description="Gas price multiplier over base fee"
    )
    
    # Circuit Breakers
    CIRCUIT_BREAKER_LIQUIDITY_DROP: float = Field(
        default=0.3,
        description="Liquidity drop threshold for circuit breaker"
    )
    CIRCUIT_BREAKER_GAS_SPIKE: int = Field(
        default=200,
        description="Gas price threshold in gwei for circuit breaker"
    )
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
    
    @validator('PRIVATE_KEY')
    def validate_private_key(cls, v):
        """Validate private key format"""
        if v and not v.startswith('0x'):
            raise ValueError('Private key must start with 0x')
        return v
    
    @validator('INITIAL_CAPITAL')
    def validate_initial_capital(cls, v):
        """Ensure initial capital is sufficient for gas fees"""
        if v < 10:
            logger.warning("Initial capital below $10 - gas fees may be problematic")
        return v

# Global configuration instance
config = TradingConfig()

@dataclass
class TradingState:
    """Trading state singleton for runtime tracking"""
    current_capital: float = config.INITIAL_CAPITAL
    positions_open: int = 0
    total_trades: int = 0
    profitable_trades: int = 0
    total_gas_spent: float = 0.0
    last_trade_time: Optional[float] = None
    circuit_breaker_active: bool = False
    
    def update_after_trade(self, profit: float, gas_cost: float):
        """Update state after trade execution"""
        self.current_capital += profit
        self.total_gas_spent += gas_cost
        self.total_trades += 1
        if profit > 0:
            self.profitable_trades += 1
        self.last_trade_time = time.time()
        
    def get_performance_metrics(self) -> dict:
        """Calculate performance metrics"""
        win_rate = (self.profitable_trades / self.total_trades) if self.total_trades > 0 else 0
        avg_profit = (self.current_capital - config.INITIAL_CAPITAL) / max(self.total_trades, 1)
        return {
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_gas_spent': self.total_gas_spent,
            'capital_remaining': self.current_capital
        }

# Initialize global state
trading_state = TradingState()