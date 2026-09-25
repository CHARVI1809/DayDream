package com.example.daydream.ui

import android.content.Context
import android.content.SharedPreferences
import android.graphics.BitmapFactory
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.io.InputStream
import java.util.Calendar

// ---------------------------------------------------------------------
// Data classes -- what we read out of story_package.json.
// ---------------------------------------------------------------------
data class Chapter(
    val day: Int,
    val title: String,
    val beat: String,
    val imageFile: String
)

data class StoryPackage(
    val title: String,
    val totalDays: Int,
    val chapters: List<Chapter>
)

// ---------------------------------------------------------------------
// Phase 6 -- date-gating logic.
//
// We store the story's "start date" (as midnight, in epoch milliseconds)
// in SharedPreferences the first time the app is ever opened. On every
// later launch we compare today's date against that stored start date to
// work out which day of the story should be unlocked -- day 1 on the
// start date itself, day 2 the next calendar day, and so on, capped at
// the story's total length once it's finished.
//
// Using plain millisecond math via Calendar (not java.time) so this
// works on any minSdk without extra Gradle setup.
// ---------------------------------------------------------------------

private const val PREFS_NAME = "daydream_prefs"
private const val KEY_START_DATE_MILLIS = "story_start_date_millis"

/** Returns midnight (00:00:00.000) of today, in the device's local time zone. */
private fun todayMidnightMillis(): Long {
    val cal = Calendar.getInstance()
    cal.set(Calendar.HOUR_OF_DAY, 0)
    cal.set(Calendar.MINUTE, 0)
    cal.set(Calendar.SECOND, 0)
    cal.set(Calendar.MILLISECOND, 0)
    return cal.timeInMillis
}

/**
 * Returns the story's start date (midnight, epoch millis). If this is the
 * very first time the app has been opened, today's date is saved as the
 * start date and returned.
 */
private fun getOrCreateStartDate(prefs: SharedPreferences): Long {
    val existing = prefs.getLong(KEY_START_DATE_MILLIS, -1L)
    if (existing != -1L) return existing

    val newStart = todayMidnightMillis()
    prefs.edit().putLong(KEY_START_DATE_MILLIS, newStart).apply()
    return newStart
}

/**
 * Computes which day of the story should currently be unlocked.
 * Day 1 on the start date itself, incrementing by 1 each following
 * calendar day, capped at totalDays once the story is complete.
 */
private fun computeCurrentDay(startDateMillis: Long, totalDays: Int): Int {
    val msPerDay = 24L * 60L * 60L * 1000L
    val daysSinceStart = ((todayMidnightMillis() - startDateMillis) / msPerDay).toInt() + 1
    return daysSinceStart.coerceIn(1, totalDays)
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val story = loadStoryPackage()

        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val startDateMillis = getOrCreateStartDate(prefs)
        val currentDay = computeCurrentDay(startDateMillis, story.totalDays)
        val isStoryComplete = currentDay >= story.totalDays &&
                computeCurrentDay(startDateMillis, Int.MAX_VALUE) > story.totalDays

        val chapter = story.chapters.first { it.day == currentDay }
        val bitmap = loadImageFromAssets(chapter.imageFile)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ChapterScreen(
                        storyTitle = story.title,
                        chapter = chapter,
                        totalDays = story.totalDays,
                        isStoryComplete = isStoryComplete,
                        bitmap = bitmap
                    )
                }
            }
        }
    }

    private fun loadStoryPackage(): StoryPackage {
        val jsonText = assets.open("story_package/story_package.json")
            .bufferedReader()
            .use { it.readText() }

        val root = JSONObject(jsonText)
        val chaptersArray = root.getJSONArray("chapters")

        val chapters = mutableListOf<Chapter>()
        for (i in 0 until chaptersArray.length()) {
            val c = chaptersArray.getJSONObject(i)
            chapters.add(
                Chapter(
                    day = c.getInt("day"),
                    title = c.getString("title"),
                    beat = c.getString("beat"),
                    imageFile = c.getString("image_file")
                )
            )
        }

        return StoryPackage(
            title = root.getString("title"),
            totalDays = root.getInt("total_days"),
            chapters = chapters
        )
    }

    private fun loadImageFromAssets(filename: String): android.graphics.Bitmap {
        val stream: InputStream = assets.open("story_package/images/$filename")
        return BitmapFactory.decodeStream(stream)
    }
}

@Composable
fun ChapterScreen(
    storyTitle: String,
    chapter: Chapter,
    totalDays: Int,
    isStoryComplete: Boolean,
    bitmap: android.graphics.Bitmap
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = storyTitle,
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = "Day ${chapter.day} of $totalDays",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = chapter.title,
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(16.dp))

        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = chapter.title,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = chapter.beat,
            fontSize = 16.sp,
            modifier = Modifier.padding(horizontal = 8.dp)
        )

        if (isStoryComplete) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "The story is complete.",
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}
