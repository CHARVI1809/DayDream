package com.daydream.app

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

// ---------------------------------------------------------------------
// Simple data classes representing one chapter and the whole story.
// Nothing fancy -- just what we read out of story_package.json.
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

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Read story_package.json from assets and parse it.
        val story = loadStoryPackage()

        // For Phase 5, we hardcode showing Day 1 -- date-gating comes in Phase 6.
        val day1 = story.chapters.first { it.day == 1 }
        val day1Bitmap = loadImageFromAssets(day1.imageFile)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ChapterScreen(storyTitle = story.title, chapter = day1, bitmap = day1Bitmap)
                }
            }
        }
    }

    /** Reads assets/story_package/story_package.json and parses it into a StoryPackage. */
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

    /** Loads a chapter's image from assets/story_package/images/<filename>. */
    private fun loadImageFromAssets(filename: String): android.graphics.Bitmap {
        val stream: InputStream = assets.open("story_package/images/$filename")
        return BitmapFactory.decodeStream(stream)
    }
}

/**
 * A single screen showing one chapter: the wallpaper image, its title,
 * and the beat text below it (this is the "tap to read" content from
 * our earlier discussion, shown directly here for Phase 5 simplicity).
 */
@Composable
fun ChapterScreen(storyTitle: String, chapter: Chapter, bitmap: android.graphics.Bitmap) {
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

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Day ${chapter.day}: ${chapter.title}",
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
    }
}
