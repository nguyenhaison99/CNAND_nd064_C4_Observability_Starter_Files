import logging
from os import getenv

from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from jaeger_client import Config
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

# MongoDB Configuration
app.config['MONGO_DBNAME'] = 'example-mongodb'
app.config['MONGO_URI'] = 'mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb'

# Initialize PyMongo
mongo = PyMongo(app)

# Prometheus Metrics Configuration
metrics = PrometheusMetrics(app, group_by='endpoint')
metrics.info('app_info', 'Application info', version='1.0.3')

# Define a counter metric for request paths
metrics.register_default(
    metrics.counter(
        'by_path_counter', 'Request count by request paths',
        labels={'path': lambda: request.path}
    )
)

# Define a counter metric for request endpoints
by_endpoint_counter = metrics.counter(
    'by_endpoint_counter', 'Request count by request endpoint',
    labels={'endpoint': lambda: request.endpoint}
)

# Jaeger Tracing Configuration
JAEGER_AGENT_HOST = getenv('JAEGER_AGENT_HOST', 'localhost')


class InvalidHandle(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        error_message = dict(self.payload or ())
        error_message['message'] = self.message
        return error_message


# Define an error handler for InvalidHandle exceptions
@app.errorhandler(InvalidHandle)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


# Initialize the Jaeger tracer
def init_tracer(service):
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
            'local_agent': {'reporting_host': JAEGER_AGENT_HOST},
        },
        service_name=service,
    )

    # This call also sets opentracing.tracer
    return config.initialize_tracer()


# Initialize the Jaeger tracer for the backend service
tracer = init_tracer('backend')


# Define a route for handling errors
@app.route('/error')
@by_endpoint_counter
def oops():
    # Simulate an internal server error
    return ':(', 500


# Define a route that raises an InvalidHandle exception
@app.route('/foo')
@by_endpoint_counter
def get_error():
    raise InvalidHandle('Error occurred', status_code=410)


# Define the homepage route
@app.route('/')
@by_endpoint_counter
def homepage():
    with tracer.start_span('hello-world'):
        # Log a trace for this span
        app.logger.info('Trace sent successfully for /hello-world')
        return "Hello World"


# Define an API route
@app.route('/api')
@by_endpoint_counter
def my_api():
    with tracer.start_span('api'):
        answer = "something"
        # Log a trace for this span
        app.logger.info('Trace sent successfully for /api')
    return jsonify(response=answer)


# Define a route for adding a star to MongoDB
@app.route('/star', methods=['POST'])
@by_endpoint_counter
def add_star():
    star = mongo.db.stars
    name = request.json['name']
    distance = request.json['distance']
    star_id = star.insert({'name': name, 'distance': distance})
    new_star = star.find_one({'_id': star_id})
    output = {'name': new_star['name'], 'distance': new_star['distance']}
    # Log a trace for this span
    app.logger.info('Trace sent successfully for /star')
    return jsonify({'result': output})


# Define a healthcheck route
@app.route('/healthz')
@by_endpoint_counter
def healthcheck():
    app.logger.info('Status request successful')
    return jsonify({"result": "OK - healthy"})


if __name__ == "__main__":
    app.run(threaded=True)
