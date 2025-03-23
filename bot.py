import discord
from discord.ext import commands
import random
import asyncio
from discord import app_commands

# 機器人設置
intents = discord.Intents.default()
intents.message_content = False
intents.members = False

bot = commands.Bot(command_prefix='/', intents=intents)

# 遊戲狀態變數
games = {}

class Player:
    def __init__(self, user):
        self.user = user
        self.hand = []
        self.roulette_chamber = [False] * 6
        self.alive = True
    
    def add_cards(self, cards):
        self.hand.extend(cards)
    
    def remove_cards_by_ids(self, card_ids):
        self.hand = [card for card in self.hand if card["id"] not in card_ids]
    
    def get_cards_by_ids(self, card_ids):
        return [card for card in self.hand if card["id"] in card_ids]
    
    def initialize_roulette(self):
        self.roulette_chamber = [False] * 6
        bullet_position = random.randint(0, 5)
        self.roulette_chamber[bullet_position] = True
    
    def pull_trigger(self):
        chamber = random.randint(0, 5)
        result = self.roulette_chamber[chamber]
        print(f"{self.user.name} 的輪盤: {self.roulette_chamber}，扣動第 {chamber + 1} 槽，結果: {'中彈' if result else '未中'}")
        if result:
            self.alive = False
            return True
        return False

class Game:
    def __init__(self, channel, host):
        self.channel = channel
        self.players = [Player(host)]
        self.started = False
        self.current_player_index = 0
        self.card_types = ["King", "Queen", "Ace", "Joker"]
        self.current_card_type = None
        self.last_play = {"player": None, "count": 0, "claimed_type": None, "played_cards": []}
    
    async def start_game(self):
        if len(self.players) < 2:
            await self.channel.send("需要至少2名玩家才能開始遊戲！")
            return False
        
        deck = []
        card_id = 1
        for card_type in self.card_types:
            if card_type == "Joker":
                for _ in range(4):
                    deck.append({"type": card_type, "id": card_id})
                    card_id += 1
            else:
                for _ in range(10):
                    deck.append({"type": card_type, "id": card_id})
                    card_id += 1
        
        random.shuffle(deck)
        
        for player in self.players:
            player.hand = deck[:5]
            deck = deck[5:]
            player.initialize_roulette()
            print(f"{player.user.name} 的輪盤: {player.roulette_chamber}")
            
            cards_message = "你的手牌:\n" + "\n".join([f"ID: {card['id']} - {card['type']}" for card in player.hand])
            try:
                await player.user.send(cards_message)
            except discord.Forbidden:
                await self.channel.send(f"{player.user.mention} 我無法發送私訊給你。請允許伺服器成員發送私訊。")
        
        self.current_card_type = random.choice(["King", "Queen", "Ace"])
        self.started = True
        random.shuffle(self.players)
        
        await self.channel.send(f"遊戲開始！本回合牌型是 **{self.current_card_type}**。 " + 
                               f"輪到 {self.players[self.current_player_index].user.mention} 出牌！")
        return True
    
    async def start_new_round(self):
        """開啟新回合：重新洗牌並刷新牌型"""
        deck = []
        card_id = 1
        for card_type in self.card_types:
            if card_type == "Joker":
                for _ in range(4):
                    deck.append({"type": card_type, "id": card_id})
                    card_id += 1
            else:
                for _ in range(10):
                    deck.append({"type": card_type, "id": card_id})
                    card_id += 1
        
        random.shuffle(deck)
        
        for player in self.players:
            if player.alive:
                player.hand = deck[:5]
                deck = deck[5:]
                cards_message = "新回合開始，你的新手牌:\n" + "\n".join([f"ID: {card['id']} - {card['type']}" for card in player.hand])
                try:
                    await player.user.send(cards_message)
                except discord.Forbidden:
                    await self.channel.send(f"{player.user.mention} 我無法發送私訊給你。請檢查私訊設置。")
        
        self.current_card_type = random.choice(["King", "Queen", "Ace"])
    
    def get_player(self, user):
        for player in self.players:
            if player.user.id == user.id:
                return player
        return None
    
    def next_player(self):
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) <= 1:
            return None
        
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        while not self.players[self.current_player_index].alive:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
        return self.players[self.current_player_index]
    
    def check_game_over(self):
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) <= 1:
            return alive_players[0] if alive_players else None
        return False

@bot.event
async def on_ready():
    print(f'{bot.user} 已連接並準備就緒！')
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 個指令")
    except Exception as e:
        print(e)

@bot.tree.command(name="start_liars_deck", description="開始一個新的說謊者牌組遊戲")
async def start_liars_deck(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in games:
        await interaction.response.send_message("此頻道已有一個進行中的遊戲！")
        return
    
    games[channel_id] = Game(interaction.channel, interaction.user)
    await interaction.response.send_message(f"說謊者牌組遊戲由 {interaction.user.mention} 發起！使用 `/join` 加入遊戲。準備就緒後，主持人可使用 `/deal` 開始。")

@bot.tree.command(name="join", description="加入一個進行中的說謊者牌組遊戲")
async def join(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in games:
        await interaction.response.send_message("此頻道目前沒有進行中的遊戲。使用 `/start_liars_deck` 開始一個遊戲")
        return
    
    game = games[channel_id]
    if game.started:
        await interaction.response.send_message("遊戲已經開始！")
        return
    
    for player in game.players:
        if player.user.id == interaction.user.id:
            await interaction.response.send_message("你已經在遊戲中！")
            return
    
    if len(game.players) >= 4:
        await interaction.response.send_message("遊戲已滿（最多4名玩家）！")
        return
    
    game.players.append(Player(interaction.user))
    await interaction.response.send_message(f"{interaction.user.mention} 已加入遊戲！（{len(game.players)}/4 名玩家）")

@bot.tree.command(name="deal", description="發牌並開始遊戲")
async def deal(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in games:
        await interaction.response.send_message("此頻道沒有進行中的遊戲。")
        return
    
    game = games[channel_id]
    if interaction.user.id != game.players[0].user.id:
        await interaction.response.send_message("只有遊戲主持人可以開始發牌！")
        return
    
    if game.started:
        await interaction.response.send_message("遊戲已經開始！")
        return
    
    await interaction.response.send_message("正在發牌並開始遊戲...")
    success = await game.start_game()
    if not success:
        del games[channel_id]

@bot.tree.command(name="hand", description="查看你的手牌（將以私訊發送）")
async def hand(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in games:
        await interaction.response.send_message("此頻道沒有進行中的遊戲。", ephemeral=True)
        return
    
    game = games[channel_id]
    player = game.get_player(interaction.user)
    if not player or not game.started:
        await interaction.response.send_message("你不在遊戲中或遊戲尚未開始！", ephemeral=True)
        return
    
    hand_message = "你的手牌:\n" + "\n".join([f"ID: {card['id']} - {card['type']}" for card in player.hand])
    await interaction.response.send_message("我已將你的手牌資訊發送到私訊。", ephemeral=True)
    await interaction.user.send(hand_message)

@bot.tree.command(name="play", description="出牌並指定牌的編號（在私訊中使用）")
@app_commands.describe(card_ids="要出的牌編號，用空格分隔（例如 '1 3 5'）")
async def play(interaction: discord.Interaction, card_ids: str):
    if not isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("請在私訊中使用此指令！", ephemeral=True)
        return
    
    player_game = None
    player_obj = None
    game_channel = None
    for channel_id, game in games.items():
        if game.started:
            player = game.get_player(interaction.user)
            if player:
                player_game = game
                player_obj = player
                game_channel = bot.get_channel(channel_id)
                break
    
    if not player_game or not player_obj.alive or player_game.players[player_game.current_player_index].user.id != interaction.user.id:
        await interaction.response.send_message("無法出牌：不在遊戲中、已淘汰或未輪到你！")
        return
    
    try:
        card_ids_list = [int(id.strip()) for id in card_ids.split()]
        if len(card_ids_list) < 1 or len(card_ids_list) > 3:
            await interaction.response.send_message("請指定 1-3 張牌的編號！")
            return
    except ValueError:
        await interaction.response.send_message("請輸入有效的牌編號（例如 '1 3 5'）！")
        return
    
    selected_cards = player_obj.get_cards_by_ids(card_ids_list)
    if len(selected_cards) != len(card_ids_list):
        await interaction.response.send_message("你指定的某些牌編號不在你的手牌中！")
        return
    
    player_game.last_play = {
        "player": player_obj,
        "count": len(card_ids_list),
        "claimed_type": player_game.current_card_type,
        "played_cards": selected_cards
    }
    
    await interaction.response.send_message(f"你聲稱出了 {len(card_ids_list)} 張 {player_game.current_card_type} 牌（編號: {card_ids}）。")
    await game_channel.send(f"{interaction.user.mention} 聲稱出了 {len(card_ids_list)} 張 **{player_game.current_card_type}** 牌。")
    
    next_player = player_game.next_player()
    if next_player:
        await game_channel.send(f"現在輪到 {next_player.user.mention} 出牌！在私訊中使用 `/play` 出牌或使用 `/liar` 質疑。")
    else:
        await game_channel.send("遊戲結束！所有玩家已被淘汰。")
        del games[game_channel.id]

@bot.tree.command(name="liar", description="質疑上一位玩家的聲明")
async def liar(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in games:
        await interaction.response.send_message("此頻道沒有進行中的遊戲。")
        return
    
    game = games[channel_id]
    player = game.get_player(interaction.user)
    if not player or not game.started or not player.alive or not game.last_play or game.last_play["player"].user.id == interaction.user.id:
        await interaction.response.send_message("無法質疑：條件不符！")
        return
    
    challenged_player = game.last_play["player"]
    count = game.last_play["count"]
    claimed_type = game.last_play["claimed_type"]
    played_cards = game.last_play["played_cards"]
    
    valid_cards = sum(1 for card in played_cards if card["type"] == claimed_type or card["type"] == "Joker")
    was_lying = valid_cards < count
    
    card_display = ", ".join([f"ID: {card['id']} - {card['type']}" for card in played_cards])
    await interaction.response.send_message(f"{interaction.user.mention} 質疑 {challenged_player.user.mention} 的聲明！\n翻開的牌: {card_display}")
    
    if was_lying:
        await interaction.channel.send(f"{challenged_player.user.mention} 說謊了！他們出的牌不符合 {count} 張 {claimed_type} 的聲明。")
        await interaction.channel.send(f"{challenged_player.user.mention} 現在必須進行俄羅斯輪盤！")
        
        shot = challenged_player.pull_trigger()
        if shot:
            await interaction.channel.send(f"💥 **砰！** {challenged_player.user.mention} 已被淘汰！")
        else:
            await interaction.channel.send(f"*喀噠* {challenged_player.user.mention} 這次倖存了！")
        
        challenged_player.remove_cards_by_ids([card["id"] for card in played_cards])
    else:
        await interaction.channel.send(f"{challenged_player.user.mention} 說的是實話！他們的牌符合 {count} 張 {claimed_type} 的聲明。")
        await interaction.channel.send(f"{interaction.user.mention} 現在必須進行俄羅斯輪盤！")
        
        shot = player.pull_trigger()
        if shot:
            await interaction.channel.send(f"💥 **砰！** {interaction.user.mention} 已被淘汰！")
        else:
            await interaction.channel.send(f"*喀噠* {interaction.user.mention} 這次倖存了！")
        
        challenged_player.remove_cards_by_ids([card["id"] for card in played_cards])
    
    # 開槍後開啟新回合
    await game.start_new_round()
    await interaction.channel.send("新回合開始！牌組已重新洗牌並分配給所有存活玩家，指定牌型已更新。請檢查私訊以查看新手牌。")
    
    winner = game.check_game_over()
    if winner:
        if winner == "None":
            await interaction.channel.send("遊戲結束！沒有玩家存活。")
        else:
            await interaction.channel.send(f"遊戲結束！{winner.user.mention} 是最後一位存活的玩家，獲得勝利！")
        del games[channel_id]
        return
    
    next_player = game.next_player()
    if next_player:
        await interaction.channel.send(f"本回合牌型為 **{game.current_card_type}**。現在輪到 {next_player.user.mention} 出牌！")
    else:
        await interaction.channel.send("遊戲結束！沒有玩家存活。")
        del games[channel_id]

@bot.tree.command(name="stop", description="強制停止當前遊戲（僅限主持人）")
async def stop_game(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id not in games:
        await interaction.response.send_message("此頻道沒有進行中的遊戲。")
        return
    
    game = games[channel_id]
    if game.players[0].user.id != interaction.user.id:
        await interaction.response.send_message("只有遊戲主持人可以強制停止遊戲！")
        return
    
    del games[channel_id]
    await interaction.response.send_message("遊戲已被停止。")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        await bot.process_commands(message)

# 運行機器人（請替換為您的 token）
bot.run('YOUR_DISCORD_TOKEN')
