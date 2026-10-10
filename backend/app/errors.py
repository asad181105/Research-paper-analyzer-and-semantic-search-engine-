from flask import jsonify


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(err):
        return jsonify(error="bad_request", message=getattr(err, "description", str(err))), 400

    @app.errorhandler(404)
    def not_found(err):
        return jsonify(error="not_found", message=getattr(err, "description", "Not found")), 404

    @app.errorhandler(409)
    def conflict(err):
        return jsonify(error="conflict", message=getattr(err, "description", str(err))), 409

    @app.errorhandler(413)
    def too_large(err):
        return jsonify(error="payload_too_large", message="File exceeds MAX_UPLOAD_MB"), 413

    @app.errorhandler(415)
    def unsupported(err):
        return jsonify(error="unsupported_media", message=getattr(err, "description", str(err))), 415

    @app.errorhandler(429)
    def ratelimit(err):
        return jsonify(error="rate_limited", message="Too many requests"), 429

    @app.errorhandler(500)
    def server_error(err):
        app.logger.exception("Unhandled error")
        return jsonify(error="internal_error", message="An unexpected error occurred"), 500
