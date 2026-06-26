#!/usr/bin/env python3
"""
Aerosmith叙事摇滚 5首 批量生成
5个主题：新征程启航、从低谷走向辉煌、虽千万人吾往矣、舔舐伤口不向命运屈服、站在山巅挑战自我
使用预写歌词直接调用music_generation，绕过AI歌词API
"""

import os
import sys
import time
import random
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minimax_music.api.lyrics import LyricsClient
from minimax_music.api.music import MusicClient
from minimax_music.config import get_api_key, detect_account_tier
from minimax_music.generators.vocal import VocalGenerator
from minimax_music.naming import generate_name_with_llm, resolve_filename_collision
from minimax_music.evidence.recorder import Recorder
from minimax_music.evidence.types import Action, Actor
from minimax_music.report.markdown import generate_report
from minimax_music.utils.clean_lyrics import clean_lyrics

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "mp3"
EVIDENCE_DIR = SCRIPT_DIR / "evidence"

# 5 prompts (已添加到 prompts_full.txt 第1640-1645行)
PROMPTS = [
    "English rock, defiant, packing worn suitcase at dawn leaving a small town behind, new journey on an empty highway to the unknown, 沙哑坚定男声, Aerosmith式叙事摇滚, slow acoustic intro building to electric rock anthem, English lyrics",
    "English rock, triumphant, crawling out of broken dreams in a dingy basement apartment, climbing one step at a time from gutter to glory under neon city lights, 沧桑爆发男声, Aerosmith式励志摇滚, gritty blues-rock progression with soaring chorus, English lyrics",
    "English rock, relentless, charging through a storm with bleeding knuckles and unbroken spirit, facing an army alone with nothing but a burning heart, 沙哑嘶吼男声, Aerosmith式战斗摇滚, driving hard rock riff with pounding drums and wailing guitar solo, English lyrics",
    "English rock, wounded, collapsed in a back alley after the fight of his life, pressing on a bleeding wound while staring at the moon whispering 'I'm not done yet', 沙哑破碎男声, Aerosmith式绝境摇滚, slow melancholic verse with raw emotional build to cathartic rock crescendo, English lyrics",
    "English rock, victorious, standing on the summit wind howling at the peak of the world, looking back at the long bloody road below and forward to an even higher mountain, 沙哑高亢男声, Aerosmith式巅峰摇滚, epic stadium rock with layered guitars and triumphant choir-like chorus, English lyrics",
]

# 预写歌词：Aerosmith式叙事摇滚（Verse/Chorus/Bridge结构，Steven Tyler风格叙事）
LYRICS = [
    # Song 1: 新征程启航
    """[Verse 1]
Folded up my worn-out map
Stuffed my dreams inside a sack
This town's got nothing left for me
Just broken sidewalks and memories
The train whistle's calling out my name
Like a preacher screaming sin and shame
I don't know where I'm gonna land
But I got freedom in these hands

[Pre-Chorus]
One last look through the rain-streaked glass
One deep breath and I'm gone at last

[Chorus]
I'm rolling out on a midnight highway
Leaving yesterday in the dust
I don't know what waits around the bend
But I know I'll make it through in the end
New road rolling under my wheels
New scars that time will heal
The dawn is breaking, I'm still alive
Watch me rise, watch me drive

[Verse 2]
The radio's playing some forgotten song
I sing along though I got it wrong
Been ten hours and a thousand miles
First time I've seen my own heart smile
Every filling station and motel sign
Is another page in this new design
I ain't the boy who walked away
I'm gonna be a man someday

[Pre-Chorus]
Every mile is a prayer I send
This journey never has to end

[Chorus]
I'm rolling out on a midnight highway
Leaving yesterday in the dust
I don't know what waits around the bend
But I know I'll make it through in the end
New road rolling under my wheels
New scars that time will heal
The dawn is breaking, I'm still alive
Watch me rise, watch me drive

[Bridge]
There ain't no map for finding your soul
No road sign saying you're finally whole
You just keep driving till the fear runs out
And find what life is all about

[Final Chorus]
Yeah I'm rolling out on a midnight highway
Burning rubber, burning doubt
Every white line is a promise I made
To the man I'm gonna be someday
New road, new scars, new sky
Watch me rise, watch me fly
""",

    # Song 2: 从低谷走向辉煌
    """[Verse 1]
Concrete floor was my bed last winter
Roaches dancing on the wall
Ate my last can of beans for dinner
Damn near lost it all
Every job I got I botched
Every door they slammed in my face
But there's a fire that doesn't die
When you've got nothing left to lose but grace

[Pre-Chorus]
I scraped my knuckles on the ground
Built my empire from the ground up sound

[Chorus]
From the gutter to the glory
I wrote my name in blood and sweat
Every step was a war story
Every scar I can't forget
They said I'd never make it
Said I'd always be the same
But I crawled out of the basement
And carved my name in the hall of fame

[Verse 2]
Got a break at a two-bit bar
Sweeping floors for minimum pay
One night the singer didn't show
And I grabbed that stage and I made it stay
Three chords and a broken voice
But the crowd went dead silent still
For the first time in my ragged life
I felt something real, something I could feel

[Pre-Chorus]
The neon lights burned through the smoke
I opened my lungs and let them choke

[Chorus]
From the gutter to the glory
I wrote my name in blood and sweat
Every step was a war story
Every scar I can't forget
They said I'd never make it
Said I'd always be the same
But I crawled out of the basement
And carved my name in the hall of fame

[Bridge]
This ain't no fairy tale, no accident
I bled for every goddamn cent
The higher I climb, the more I see
The gutter made me, and it set me free

[Final Chorus]
From the gutter to the glory
Now I'm standing in the light
Every doubter's got a front-row seat
Watching a loser win the fight
Yeah I crawled out of the basement
And I ain't ever going back
From the gutter to the glory
I'm never looking back
""",

    # Song 3: 虽千万人吾往矣
    """[Verse 1]
Thunder rolling in my chest
Lightning cracking in my brain
They got their armies, got their guns
I got nothing but hurricane
A hundred men against one soul
The odds ain't pretty, I know
But I've been fighting since the day I was born
And I ain't about to let it go

[Pre-Chorus]
You think the numbers scare me?
You think I'll bow and break?
I've walked through fire with frozen feet
For heaven's and hell's sake

[Chorus]
I'm standing my ground, I'm holding the line
With bleeding knuckles and a fractured spine
They can bring their whole damn cavalry
But they'll have to go through me
One against a thousand, I like those odds
I'll fight their angels and I'll fight their gods
The storm is coming, let it rain
I'll die standing, not on my knees again

[Verse 2]
My father said I was born too stubborn
My mother said I'd never learn
But when you're raised on broken promises
There's only one direction you can turn
Straight ahead, through the wall
Through the fire, through it all
I didn't come this far to turn around
I'm gonna shake this whole goddamn ground

[Pre-Chorus]
You think I'm crazy? Maybe so
But crazy's the only way I know

[Chorus]
I'm standing my ground, I'm holding the line
With bleeding knuckles and a fractured spine
They can bring their whole damn cavalry
But they'll have to go through me
One against a thousand, I like those odds
I'll fight their angels and I'll fight their gods
The storm is coming, let it rain
I'll die standing, not on my knees again

[Bridge]
Every soldier who has stood alone
Who faced the dark on his own
This one's for the broken few
Who never knew how to lose

[Guitar Solo Build]

[Final Chorus]
I'm standing my ground, I'm holding the line
This heart of mine is a battle sign
Let 'em come with fire and sword
I am my own reward
One against a thousand, I still like those odds
I'll fight your angels and I'll fight your gods
When the dust settles and the smoke clears
I'll still be standing after all these years
""",

    # Song 4: 舔舐伤口不向命运屈服
    """[Verse 1]
Back against the cold brick wall
Blood trickling down my chin
The fight left me in this alley
With nothing but the state I'm in
My ribs are cracked, my spirit's torn
The streetlight flickers like a dying flame
Every breath is a reminder
That I lost the game again

[Pre-Chorus]
But somewhere deep inside this wreck
There's a pulse that won't disconnect

[Chorus]
I'm not done yet, I'm not done yet
You hear me moon up in the sky?
I may be crawling, I may be broken
But I ain't ready to die
Kick the dirt and taste the rust
Dust yourself off from the dust
I'm not done yet, not done yet
I've got more fight left in my chest

[Verse 2]
This ain't the first time I've hit the floor
Ain't the first time I've tasted defeat
But every time they count me out
I find the strength to get back to my feet
The scars are just a roadmap
Of everywhere I've been before
And every wound that's bleeding now
Is a door I'm walking through, not a closing door

[Pre-Chorus]
The moon is cold but it's still bright
And I'm still breathing in this night

[Chorus]
I'm not done yet, I'm not done yet
You hear me moon up in the sky?
I may be crawling, I may be broken
But I ain't ready to die
Kick the dirt and taste the rust
Dust yourself off from the dust
I'm not done yet, not done yet
I've got more fight left in my chest

[Bridge]
I'll stitch my wounds with broken thread
I'll rest my bones upon this stone
But when the morning sun arrives
I'll drag myself back to the throne
Because quitting ain't in my blood
And surrender ain't my name
The same fire that burned me down
Is gonna light my way to fame

[Final Chorus]
I'm not done yet, I'm not done yet
The world can hit me with its best shot
Knock me down a million times
I'll get up every time I'm not
Not done yet, not done yet
I'll crawl, I'll bleed, I'll fight, I'll sweat
But I'm not done yet
No, I'm not done yet
""",

    # Song 5: 站在山巅挑战自我
    """[Verse 1]
Here I am, standing on the top
Wind screaming in my ears
The path behind is stained with blood
A trail of sweat and tears
I can see the valley where I started
So far below, so far away
Every mountain I had to climb
Every price I had to pay

[Pre-Chorus]
But something strange is happening now
Standing here at the peak
I'm not satisfied somehow
There's a voice I cannot speak

[Chorus]
I climbed the highest mountain
I reached the endless sky
But now that I'm on the summit
I'm asking myself why
There's always one more peak to climb
One more dream to chase
The summit ain't the finish line
It's just another starting place

[Verse 2]
I thought the view would make me whole
Thought the glory would be sweet
But all I feel is restless fire
Burning in my feet
The trophies on my shelf don't sing
The medals don't embrace
The only thing that matters now
Is the hunger on my face

[Pre-Chorus]
I've beaten every challenger
I've silenced every doubt
But the hardest fight is waiting still
The one within, without

[Chorus]
I climbed the highest mountain
I reached the endless sky
But now that I'm on the summit
I'm asking myself why
There's always one more peak to climb
One more dream to chase
The summit ain't the finish line
It's just another starting place

[Bridge]
There's a mirror on this mountaintop
And the man I see inside
Is asking me if I'm brave enough
To let go of my pride
To start again from zero
When I've already won it all
To tear it down and build again
And answer a harder call

[Final Chorus]
So I'm climbing past the summit now
Into the empty blue
There ain't a mountain high enough
For what I'm born to do
The summit ain't the finish line
The top is just the floor
I'll keep on climbing, reaching, fighting
Always wanting more
Yeah, always wanting more
""",
]


def main():
    print("=" * 60)
    print("Aerosmith叙事摇滚 5首 (预写歌词)")
    print("=" * 60)

    api_key = get_api_key()
    tier = detect_account_tier(api_key)
    print(f"Account tier: {tier}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    music_client = MusicClient(api_key)
    lyrics_client = LyricsClient(api_key)
    vocal_gen = VocalGenerator(music_client, lyrics_client)
    recorder = Recorder(evidence_dir=EVIDENCE_DIR)

    used_names: set[str] = set()
    success_count = 0
    failed_tasks: list[tuple[int, str]] = []
    completed: list[tuple[str, str]] = []

    for i, (prompt, lyrics) in enumerate(zip(PROMPTS, LYRICS)):
        print(f"\n[{i+1}/5] 处理: {prompt[:60]}...")

        recorder.record(
            action=Action.PROMPT_CREATE,
            actor=Actor.HUMAN,
            input_data={"line": i + 1, "prompt": prompt[:100], "instrumental": False},
        )

        recorder.record(
            action=Action.LYRICS_GENERATE,
            actor=Actor.HUMAN,
            input_data={"line": i + 1, "prompt": "human-pre-written"},
            output_data={"title": None, "lyrics_length": len(lyrics)},
        )

        base_name = generate_name_with_llm(api_key, prompt)
        if not base_name:
            base_name = f"aerosmith_narrative_{i+1}"
        base_name = base_name.replace(" ", "_")
        final_base = resolve_filename_collision(base_name, OUTPUT_DIR, ".mp3", used_names)
        used_names.add(final_base)

        (OUTPUT_DIR / f"{final_base}.txt").write_text(lyrics, encoding="utf-8")
        (OUTPUT_DIR / f"{final_base}_pure.txt").write_text(clean_lyrics(lyrics), encoding="utf-8")
        with open(OUTPUT_DIR / "song_lyrics_mapping.txt", 'a', encoding='utf-8') as f:
            f.write(f"{final_base} -> {final_base}.txt | {prompt[:80]}\n")

        try:
            result = vocal_gen.generate(
                prompt=prompt,
                use_ai_lyrics=False,
                user_lyrics=lyrics,
                output_dir=OUTPUT_DIR,
                no_format_prompt=True,
                song_title=final_base,
                save_lyrics_file=False,
                skip_collision_check=True,
            )
            recorder.record(
                action=Action.MUSIC_GENERATE,
                actor=Actor.AI,
                input_data={"prompt": prompt[:100]},
                output_data={"file": Path(result.audio_path).name, "duration_ms": result.duration_ms},
            )
            print(f"  ✓ 成功: {Path(result.audio_path).name}")

            try:
                report_path = generate_report(EVIDENCE_DIR, OUTPUT_DIR, final_base, prompt, is_instrumental=False)
                zip_path = OUTPUT_DIR / f"{final_base}-版权报告.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(report_path, report_path.name)
                recorder.record(
                    action=Action.REPORT_GENERATE,
                    actor=Actor.HUMAN_AI,
                    output_data={"report": report_path.name, "zip": zip_path.name},
                )
                print(f"  ✓ 报告: {report_path.name}")
            except Exception as e:
                print(f"  ⚠ 报告失败: {e}")

            success_count += 1
            completed.append((final_base, prompt))
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed_tasks.append((i + 1, prompt))

        if i < len(PROMPTS) - 1:
            delay = random.randint(2, 5)
            print(f"  等待 {delay}s...")
            time.sleep(delay)

    print("\n" + "=" * 60)
    print(f"完成: {success_count}/5 成功")
    if failed_tasks:
        print("失败:")
        for idx, p in failed_tasks:
            print(f"  [{idx}] {p[:50]}...")
    if completed:
        print("\n生成的歌曲:")
        for name, p in completed:
            print(f"  {name}")
    print("=" * 60)
    return 0 if not failed_tasks else 1


if __name__ == "__main__":
    sys.exit(main())
