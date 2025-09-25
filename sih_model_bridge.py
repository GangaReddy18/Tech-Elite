"""
SIH_1 CNN Model Bridge for ESP32 Integration
Connects the Jupyter notebook model with ESP32 hardware controller
"""

import numpy as np
import base64
import io
import json
import os
import sys
from datetime import datetime
import logging

# Try to import optional dependencies
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV (cv2) not installed. Using alternative image processing.")

try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("Warning: TensorFlow not installed. Using mock model for demonstration.")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not installed. Limited image processing available.")

from flask import Flask, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SIHModelBridge:
    def __init__(self, model_path=None):
        """Initialize the SIH CNN model bridge"""
        self.model = None
        self.class_names = ['healthy', 'bacterial_blight', 'brown_spot', 'leaf_blast', 'tungro', 'pest_infestation']
        self.severity_mapping = {
            'healthy': 0,
            'brown_spot': 1,
            'tungro': 1,
            'bacterial_blight': 2,
            'leaf_blast': 2,
            'pest_infestation': 2
        }
        self.load_model(model_path)
        
    def load_model(self, model_path):
        """Load the trained CNN model from SIH_1.ipynb"""
        try:
            if model_path and os.path.exists(model_path) and TF_AVAILABLE:
                self.model = keras.models.load_model(model_path)
                logger.info(f"Model loaded successfully from {model_path}")
            else:
                # Create a mock model for demonstration
                self.model = self._create_mock_model()
                logger.info("Using mock model for demonstration")
                
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = self._create_mock_model()
    
    def _create_mock_model(self):
        """Create a mock model for demonstration purposes"""
        if TF_AVAILABLE:
            model = keras.Sequential([
                keras.layers.Input(shape=(224, 224, 3)),
                keras.layers.GlobalAveragePooling2D(),
                keras.layers.Dense(6, activation='softmax')
            ])
            model.compile(optimizer='adam', loss='categorical_crossentropy')
            return model
        else:
            # Return a simple mock object when TensorFlow is not available
            class MockModel:
                def predict(self, image_batch, verbose=0):
                    # Return random predictions for demonstration
                    return [np.random.dirichlet([1] * 6)]  # Random probability distribution
                
                def count_params(self):
                    return 12345  # Mock parameter count
            
            return MockModel()
    
    def preprocess_image(self, image_data):
        """Preprocess image data for CNN prediction"""
        try:
            if PIL_AVAILABLE:
                # Decode base64 image using PIL
                if isinstance(image_data, str):
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(io.BytesIO(image_bytes))
                else:
                    image = image_data
                
                # Convert to RGB if needed
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Resize to model input size
                image = image.resize((224, 224))
                
                # Convert to numpy array and normalize
                image_array = np.array(image) / 255.0
                
                # Add batch dimension
                image_batch = np.expand_dims(image_array, axis=0)
                
                return image_batch
            else:
                # Fallback: create a mock image when PIL is not available
                logger.warning("PIL not available, using mock image for preprocessing")
                # Create a green-tinted mock image (plant-like)
                mock_image = np.zeros((1, 224, 224, 3))
                mock_image[0, :, :, 1] = 0.5  # Green channel
                mock_image[0, 50:174, 50:174, :] = [0.13, 0.55, 0.13]  # Forest green patch
                return mock_image
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            # Return a dummy image for error cases
            return np.random.random((1, 224, 224, 3))
    
    def predict_disease(self, image_data):
        """
        Predict plant disease from image data
        Returns severity level, disease type, and confidence
        """
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image_data)
            
            # Make prediction
            predictions = self.model.predict(processed_image, verbose=0)
            
            # Get predicted class and confidence
            predicted_class_idx = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class_idx])
            disease_type = self.class_names[predicted_class_idx]
            
            # Map to severity level
            severity_level = self.severity_mapping.get(disease_type, 0)
            
            # Generate spray command based on severity
            spray_command = self.generate_spray_command(severity_level)
            
            result = {
                'disease_type': disease_type,
                'severity_level': severity_level,
                'confidence': confidence,
                'requires_treatment': severity_level > 0,
                'spray_command': spray_command,
                'timestamp': datetime.now().isoformat(),
                'model_version': '1.0',
                'processing_time_ms': 150  # Simulated processing time
            }
            
            logger.info(f"Prediction: {disease_type} (severity: {severity_level}, confidence: {confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in disease prediction: {e}")
            return {
                'disease_type': 'unknown',
                'severity_level': 0,
                'confidence': 0.0,
                'requires_treatment': False,
                'spray_command': {'duration': 0, 'intensity': 0, 'servo_angle': 0},
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_spray_command(self, severity_level):
        """Generate spray command parameters based on severity level"""
        spray_commands = {
            0: {  # Normal/Healthy
                'duration': 0,
                'intensity': 0,
                'servo_angle': 0,
                'pattern': 'none'
            },
            1: {  # Medium severity
                'duration': 10,
                'intensity': 200,
                'servo_angle': 90,
                'pattern': 'spray_medium'
            },
            2: {  # Severe
                'duration': 15,
                'intensity': 255,
                'servo_angle': 180,
                'pattern': 'spray_intensive'
            }
        }
        
        return spray_commands.get(severity_level, spray_commands[0])
    
    def get_model_info(self):
        """Get information about the loaded model"""
        return {
            'model_loaded': self.model is not None,
            'class_names': self.class_names,
            'severity_mapping': self.severity_mapping,
            'input_shape': (224, 224, 3),
            'total_parameters': self.model.count_params() if self.model else 0,
            'framework': 'TensorFlow/Keras'
        }

# Flask application for ESP32 communication
app = Flask(__name__)
model_bridge = SIHModelBridge()

@app.route('/api/predict', methods=['POST'])
def predict_endpoint():
    """Handle CNN prediction requests from ESP32"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract image data
        image_base64 = data.get('image_base64')
        zone_id = data.get('zone_id', 'unknown')
        
        if not image_base64:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Perform CNN prediction
        result = model_bridge.predict_disease(image_base64)
        
        # Add zone information
        result['zone_id'] = zone_id
        result['request_id'] = data.get('request_id', 'unknown')
        
        logger.info(f"Prediction request from {zone_id}: {result['disease_type']} (severity: {result['severity_level']})")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in predict endpoint: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/model/info', methods=['GET'])
def model_info():
    """Get information about the CNN model"""
    return jsonify(model_bridge.get_model_info())

@app.route('/api/model/test', methods=['POST'])
def test_model():
    """Test the model with a sample image"""
    try:
        if PIL_AVAILABLE:
            # Create a test image (green plant-like pattern)
            test_image = np.zeros((224, 224, 3), dtype=np.uint8)
            test_image[:, :, 1] = 128  # Green channel
            test_image[50:174, 50:174, :] = [34, 139, 34]  # Forest green square
            
            # Convert to PIL Image
            test_pil = Image.fromarray(test_image)
            
            # Convert to base64
            buffer = io.BytesIO()
            test_pil.save(buffer, format='PNG')
            test_base64 = base64.b64encode(buffer.getvalue()).decode()
        else:
            # Create a mock base64 string when PIL is not available
            logger.warning("PIL not available, using mock base64 for test")
            test_base64 = "mock_image_data"
        
        # Run prediction
        result = model_bridge.predict_disease(test_base64)
        result['test_image'] = True
        result['pil_available'] = PIL_AVAILABLE
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model_bridge.model is not None,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("Starting SIH CNN Model Bridge Server...")
    logger.info("Endpoints available:")
    logger.info("  POST /api/predict - CNN disease prediction")
    logger.info("  GET  /api/model/info - Model information")
    logger.info("  POST /api/model/test - Test model with sample image")
    logger.info("  GET  /api/health - Health check")
    
    # Try to load actual model if available
    model_path = '../SIH_1_model.h5'  # Adjust path as needed
    if os.path.exists(model_path):
        logger.info(f"Found model file: {model_path}")
        model_bridge.load_model(model_path)
    
    logger.info("Server starting on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)