import os
import keep_alive # 後で作成するファイルです
import discord
from discord import app_commands # ★これをファイルの上のほう(importの並び)に追加
from discord.ext import commands, tasks
from discord import ui # モーダル作成に必要
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import datetime
from zoneinfo import ZoneInfo

# --------------------------------------------------
# 1. Googleスプレッドシートの認証設定
# --------------------------------------------------
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# スプレッドシートのURL（/d/ と /edit の間の文字列）を指定
SPREADSHEET_KEY = '1G3xpH0d1dUM3DpDe0tY4j_woTdSYAp_9R-7QymcSOVc'
sheet = client.open_by_key(SPREADSHEET_KEY).sheet1

# --------------------------------------------------
# 2. Discord Botの設定
# --------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 通知を送るDiscordチャンネルのID（対象チャンネルを右クリックしてIDをコピー）
CHANNEL_ID = 1494211352342823013
REPORT_CHANNEL_ID = 1494211401768505474 
# DISCORD_TOKEN = ''
DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
@bot.event
async def on_ready():
    # スラッシュコマンドをDiscordに同期する（必須）
    await bot.tree.sync()
    print(f'{bot.user} がログインしました！')
    daily_reminder.start() # 定期実行タスクの開始

# --- コマンド1: タスク追加 (/add) ---
# --- コマンド1: タスク追加 (/add) ---
@bot.tree.command(name="add", description="新しいタスクを追加します")
@app_commands.describe(
    task_name="タスクの内容", 
    deadline="締め切り日 (例: 4/25)",
    category="タスクのカテゴリを選択してください"
)
# カテゴリの選択肢（ドロップダウン）を定義
@app_commands.choices(
    category=[
        app_commands.Choice(name="日調ongoing", value="日調ongoing"),
        app_commands.Choice(name="arliss", value="arliss"),
        app_commands.Choice(name="astrocamp", value="astrocamp"),
        app_commands.Choice(name="spexa", value="spexa"),
        app_commands.Choice(name="space-academy", value="space-academy"),
        app_commands.Choice(name="応用技術勉強会", value="応用技術勉強会"),
        app_commands.Choice(name="yuiproject", value="yuiproject"),
        app_commands.Choice(name="授業", value="授業"),
        app_commands.Choice(name="sgjp", value="sgjp"),
        app_commands.Choice(name="その他", value="その他"),
        app_commands.Choice(name="private", value="private")
    ]
)
async def add(interaction: discord.Interaction, task_name: str, deadline: str, category: app_commands.Choice[str]):
    # 1. 指定したチャンネル（todo報告）以外での実行を弾く
    if interaction.channel_id != REPORT_CHANNEL_ID:
        await interaction.response.send_message(f"⚠️ タスクの追加は <#{REPORT_CHANNEL_ID}> チャンネルでのみ可能です。", ephemeral=True)
        return

    # 選択されたカテゴリの値を取得
    selected_category = category.value 

    try:
        # 2. スプレッドシートに書き込み (A:タスク名, B:締め切り, C:カテゴリ)
        sheet.append_row([task_name, deadline, selected_category])

        # 3. 報告用チャンネルに通知を送る
        report_channel = interaction.client.get_channel(REPORT_CHANNEL_ID)
        
        # 本人への応答
        await interaction.response.send_message(f'スプレッドシートに「{task_name}」を登録しました。', ephemeral=True)

        # 報告用チャンネルへの投稿
        if report_channel:
            embed = discord.Embed(title="📌 新規タスク追加", color=discord.Color.blue())
            embed.add_field(name="内容", value=task_name, inline=False)
            embed.add_field(name="締め切り", value=deadline, inline=True)
            embed.add_field(name="カテゴリ", value=selected_category, inline=True)
            await report_channel.send(embed=embed)
            
    except Exception as e:
        await interaction.response.send_message(f'エラーが発生しました: {e}', ephemeral=True)


# --- コマンド2: タスク完了・削除 (/done) ---
# --- コマンド2: タスク完了・削除 (/done) ---
@bot.tree.command(name="done", description="タスクを完了して削除します")
@app_commands.describe(
    category="完了したタスクのカテゴリを選択してください",
    task_name="完了したタスク名を入力してください"
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="日調ongoing", value="日調ongoing"),
        app_commands.Choice(name="arliss", value="arliss"),
        app_commands.Choice(name="astrocamp", value="astrocamp"),
        app_commands.Choice(name="spexa", value="spexa"),
        app_commands.Choice(name="space-academy", value="space-academy"),
        app_commands.Choice(name="応用技術勉強会", value="応用技術勉強会"),
        app_commands.Choice(name="yuiproject", value="yuiproject"),
        app_commands.Choice(name="授業", value="授業"),
        app_commands.Choice(name="sgjp", value="sgjp"),
        app_commands.Choice(name="その他", value="その他"),
        app_commands.Choice(name="private", value="private")
    ]
)
async def done(interaction: discord.Interaction, category: app_commands.Choice[str], task_name: str):
    # 1. チャンネル制限
    if interaction.channel_id != REPORT_CHANNEL_ID:
        await interaction.response.send_message(f"⚠️ タスクの完了報告は <#{REPORT_CHANNEL_ID}> チャンネルでのみ可能です。", ephemeral=True)
        return

    selected_category = category.value

    try:
        # 2. スプレッドシートの全データを取得
        rows = sheet.get_all_values()
        
        target_row_index = -1
        # 2行目から順に検索（タスク名とカテゴリが両方一致する行を探す）
        for i, row in enumerate(rows):
            if i == 0: continue # ヘッダー
            # row[0]がタスク名、row[2]がカテゴリ
            if len(row) >= 3 and row[0] == task_name and row[2] == selected_category:
                target_row_index = i + 1 # gspreadは1始まりのため
                break

        if target_row_index != -1:
            # 3. 行を削除
            sheet.delete_rows(target_row_index)

            # 4. 報告用チャンネルに通知を送る
            report_channel = interaction.client.get_channel(REPORT_CHANNEL_ID)
            await interaction.response.send_message(f'「{task_name} ({selected_category})」を完了として削除しました。', ephemeral=True)

            if report_channel:
                embed = discord.Embed(title="✅ タスク完了報告", color=discord.Color.green())
                embed.add_field(name="内容", value=task_name, inline=False)
                embed.add_field(name="カテゴリ", value=selected_category, inline=True)
                embed.set_footer(text=f"完了者: {interaction.user.display_name}")
                await report_channel.send(embed=embed)
        else:
            await interaction.response.send_message(f'⚠️ カテゴリ「{selected_category}」の中に「{task_name}」というタスクは見つかりませんでした。', ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f'エラーが発生しました: {e}', ephemeral=True)

jst = ZoneInfo("Asia/Tokyo")
target_time = datetime.time(hour=9, minute=0, tzinfo=jst)

# --- 定期実行: 毎朝9時にリマインド ---
# --- 定期実行: 毎朝9時にリマインド ---
# --- 定期実行: 毎朝9時にリマインド ---
@tasks.loop(time=target_time)
async def daily_reminder():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        return

    data = sheet.get_all_values()
    if len(data) <= 1:
        return
        
    # 日付ごとにタスクをまとめる辞書を作成
    tasks_by_date = {}
    
    for i, row in enumerate(data):
        if i == 0: 
            continue # ヘッダーをスキップ
            
        if len(row) >= 2:
            t_name = row[0]
            t_deadline = row[1] if row[1] != "" else "未設定"
            t_category = row[2] if len(row) >= 3 and row[2] != "" else "未分類"
            
            if t_deadline not in tasks_by_date:
                tasks_by_date[t_deadline] = {}
                
            if t_category not in tasks_by_date[t_deadline]:
                tasks_by_date[t_deadline][t_category] = []
                
            tasks_by_date[t_deadline][t_category].append(t_name)
            
    if not tasks_by_date:
        return

    def sort_date(date_str):
        try:
            return (0, datetime.datetime.strptime(date_str, "%m/%d"))
        except ValueError:
            return (1, date_str)

    sorted_dates = sorted(tasks_by_date.keys(), key=sort_date)

    # 送信メッセージの組み立て
    reminder_msg = "おはようございます！現在残っているタスクです：\n\n"
    
    for date in sorted_dates:
        reminder_msg += f"**📅 【 {date} 】**\n"
        for category, tasks in tasks_by_date[date].items():
            reminder_msg += f"■ {category}\n"
            for task in tasks:
                # Discordの箇条書き判定を避けるため「・」を使用し、全角スペースで字下げ
                reminder_msg += f"　・ {task}\n"
        
        # 次の日付ブロックとの間だけ1行空ける
        reminder_msg += "\n" 
            
    await channel.send(reminder_msg)

# --------------------------------------------------
# Botの起動
# --------------------------------------------------

# --------------------------------------------------
# Botの起動
# --------------------------------------------------
keep_alive.keep_alive() # 追加：Webサーバーを起動してRenderを動かし続ける
bot.run(DISCORD_TOKEN)