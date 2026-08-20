package com.aysenuryesilova.ezanvakti

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.ComponentName
import android.os.SystemClock
import android.widget.RemoteViews

class NamazVaktiWidget : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            appWidgetManager.updateAppWidget(appWidgetId, createViews(context))
        }
    }

    companion object {
        fun refresh(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, NamazVaktiWidget::class.java)
            val ids = manager.getAppWidgetIds(component)
            for (id in ids) manager.updateAppWidget(id, createViews(context))
        }

        private fun createViews(context: Context): RemoteViews {
            val prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
            val location = prefs.getString("flutter.widget_location", "İstanbul (Kadıköy)")
            val nextPrayer = prefs.getString("flutter.widget_next_prayer", "Sıradaki Vakte Kalan Süre")
            val hadis = prefs.getString("flutter.widget_hadis", "📖 Günün Hadisi: 'Kolaylaştırınız, zorlaştırmayınız; müjdeleyiniz, nefret ettirmeyiniz.' (Buhârî)")
            val targetMs = prefs.getLong("flutter.widget_target_ms", 0L)

            return RemoteViews(context.packageName, R.layout.namaz_vakti_widget).apply {
                setTextViewText(R.id.widget_location, "🕌 Ezan Vakti - $location")
                setTextViewText(R.id.widget_next_vakit, nextPrayer)
                setTextViewText(R.id.widget_hadis, hadis)

                if (targetMs > System.currentTimeMillis()) {
                    val base = SystemClock.elapsedRealtime() + (targetMs - System.currentTimeMillis())
                    setChronometer(R.id.widget_chronometer, base, null, true)
                } else {
                    setChronometer(R.id.widget_chronometer, SystemClock.elapsedRealtime(), null, true)
                }
            }
        }
    }
}
