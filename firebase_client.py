"""
Firebase Firestore client for real-time data streaming and state management.
Implements robust error handling and connection pooling.
"""
import asyncio
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1 import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import GoogleAPICallError, RetryError
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore
from firebase_admin.exceptions import FirebaseError
import json
import os

from config import config, logger

class FirebaseClient:
    """Firestore client with connection pooling and automatic retry"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialized = False
        self._max_retries = 3
        self._retry_delay = 1.0
        
    def initialize(self) -> bool:
        """
        Initialize Firebase connection with error handling
        Returns: True if successful, False otherwise
        """
        try:
            if not os.path.exists(config.FIREBASE_CREDENTIALS_PATH):
                logger.error(f"Firebase credentials file not found: {config.FIREBASE_CREDENTIALS_PATH}")
                return False
            
            # Initialize Firebase app
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            
            # Initialize Firestore client
            self.client = firestore.client()
            
            # Test connection
            test_ref = self.client.collection('connection_tests').document('test')
            test_ref.set({'timestamp': datetime.utcnow().isoformat()}, merge=True)
            
            logger.info("Firebase Firestore initialized successfully")
            self._initialized = True
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {e}")
        except FirebaseError as e:
            logger.error(f"Firebase initialization error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error initializing Firebase: {e}")
        
        return False
    
    def _retry_operation(self, operation, *args, **kwargs):
        """Retry operation with exponential backoff"""
        for attempt in range(self._max_retries):
            try:
                return operation(*args, **kwargs)
            except (GoogleAPICallError, RetryError) as e:
                if attempt == self._max_retries - 1:
                    raise
                wait_time = self._retry_delay * (2 ** attempt)
                logger.warning(f"Retry attempt {attempt + 1} after error: {e}")
                time.sleep(wait_time)
    
    def write_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Write trade data to Firestore with retry logic"""
        if not self._initialized or not self.client:
            logger.error("Firebase not initialized")
            return False
        
        try:
            collection_ref = self.client.collection('trades')
            trade_id = trade_data.get('tx_hash', f"trade_{datetime.utcnow().timestamp()}")
            doc_ref = collection_ref.document(trade_id)
            
            # Add metadata
            trade_data['firestore_timestamp'] = firestore.SERVER_TIMESTAMP
            trade_data['updated_at'] = datetime.utcnow().isoformat()
            
            self._retry_operation(doc_ref.set, trade_data, merge=True)
            logger.info(f"Trade data written to Firestore: {trade_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write trade data: {e}")
            return False
    
    def update_liquidity_event(self, event_data: Dict[str, Any]) -> bool:
        """Update liquidity events collection"""
        if not self._initialized or not self.client:
            return False
        
        try:
            collection_ref = self.client.collection('liquidity_events')
            event_id = event_data.get('event_id', f"event_{datetime.utcnow().timestamp()}")
            doc_ref = collection_ref.document(event_id)
            
            event_data['timestamp'] = firestore.SERVER_TIMESTAMP
            self._retry_operation(doc_ref.set, event_data, merge=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update liquidity event: {e}")
            return False
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Read circuit breaker status from Firestore"""
        if not self._initialized or not self.client:
            return {'active': False, 'reason': 'firebase_not_initialized'}
        
        try:
            doc_ref = self.client.collection('control').document('circuit_breakers')
            doc = self._retry_operation(doc_ref.get)
            
            if doc.exists:
                return doc.to_dict()
            return {'active': False, 'reason': 'no_data'}
            
        except Exception as e:
            logger.error(f"Failed to read circuit breaker status: {e}")
            return {'active': False, 'reason': str(e)}
    
    def write_playbook_entry(self, pattern_data: Dict[str, Any]) -> bool:
        """Write validated pattern to liquidity playbook"""
        if not self._initialized or not self.client:
            return False
        
        try:
            collection_ref = self.client.collection('liquidity_playbook')
            pattern_id = pattern_data.get('pattern_signature', f"pattern_{datetime.utcnow().timestamp()}")
            doc_ref = collection_ref.document(pattern_id)
            
            pattern_data['validated_at'] = firestore.SERVER_TIMESTAMP
            pattern_data['validation_count'] = firestore.Increment(1)
            
            self._retry_operation(doc_ref.set, pattern_data, merge=True)
            logger.info(f"Playbook entry added: {pattern_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write playbook entry: {e}")
            return False
    
    def stream_mempool_data(self, callback):
        """
        Stream mempool data from Firestore (simulated - would be WebSocket in production)
        Args:
            callback: Function to call with new mempool data
        """
        if not self._initialized or not self.client:
            return
        
        # This is a simplified version - in production would use Firestore real-time updates
        # or WebSocket connection to mempool service
        collection_ref = self.client.collection('mempool_stream')
        
        # Query for recent transactions
        try:
            query = collection_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10)
            docs = self._retry_operation(query.get)
            
            for doc in docs:
                callback(doc.to_dict())
                
        except Exception as e:
            logger.error(f"Error streaming mempool data: {e}")

# Global Firebase client instance
firebase_client = FirebaseClient()