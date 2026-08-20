package com.aysenuryesilova.ezanvakti

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.aysenuryesilova.ezanvakti/widget")
            .setMethodCallHandler { call, result ->
                if (call.method == "refreshWidget") {
                    NamazVaktiWidget.refresh(this)
                    result.success(null)
                } else {
                    result.notImplemented()
                }
            }
    }
}
