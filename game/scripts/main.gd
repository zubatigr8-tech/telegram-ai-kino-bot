extends Node3D
## Turon MMA — asosiy jang sahnasi.
## Ring, jangchilar, kamera, raundlar va hakamlar qarorini boshqaradi.

enum MatchState { INTRO, FIGHT, ROUND_END, MATCH_END }

const ROUNDS := 3
const ROUND_TIME := 90.0
const RING_RADIUS := 5.0
const START_X := 1.5
const CAMERA_MAX_RADIUS := 4.7

const KEYS := {
	"move_left": [KEY_A, KEY_LEFT],
	"move_right": [KEY_D, KEY_RIGHT],
	"move_up": [KEY_W, KEY_UP],
	"move_down": [KEY_S, KEY_DOWN],
	"jab": [KEY_J],
	"cross": [KEY_K],
	"hook": [KEY_L],
	"uppercut": [KEY_U],
	"low_kick": [KEY_I],
	"high_kick": [KEY_O],
	"block": [KEY_SPACE],
	"dodge": [KEY_SHIFT],
}

var player: Fighter
var bot: Fighter
var hud: HUD
var camera: Camera3D

var _state: MatchState = MatchState.INTRO
var _state_time := 0.0
var _round := 1
var _time_left := ROUND_TIME
var _round_damage := [0.0, 0.0]  # [o'yinchi bergan, bot bergan]
var _scores := [0, 0]
var _shake := 0.0
var _winner: Fighter


func _ready() -> void:
	randomize()
	_setup_input()
	_build_environment()
	_build_ring()
	_spawn_fighters()
	_build_camera()

	hud = HUD.new()
	add_child(hud)
	hud.set_names(player.fighter_name, bot.fighter_name)
	hud.restart_pressed.connect(func(): get_tree().reload_current_scene())

	var pc := PlayerController.new()
	pc.fighter = player
	pc.joystick = hud.joystick
	add_child(pc)

	var ai := AIController.new()
	ai.fighter = bot
	ai.difficulty = 0.45
	add_child(ai)

	_start_round()


func _setup_input() -> void:
	for action in KEYS:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for key in KEYS[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			InputMap.action_add_event(action, ev)


# ---------------------------------------------------------------------------
# Sahna qurilishi
# ---------------------------------------------------------------------------

func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.02, 0.04)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.45, 0.45, 0.55)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-70, 30, 0)
	sun.light_energy = 1.1
	sun.shadow_enabled = true
	add_child(sun)

	# Ring tepasidagi projektorlar
	for i in 4:
		var spot := OmniLight3D.new()
		var a := TAU * i / 4.0 + PI / 4.0
		spot.position = Vector3(cos(a) * 3.0, 6.0, sin(a) * 3.0)
		spot.omni_range = 12.0
		spot.light_energy = 0.8
		spot.light_color = Color(1.0, 0.95, 0.85)
		add_child(spot)


func _build_ring() -> void:
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.82, 0.82, 0.8)
	floor_mat.roughness = 0.9

	# Sakkiz burchakli ring poli
	var floor_mesh := CylinderMesh.new()
	floor_mesh.top_radius = RING_RADIUS
	floor_mesh.bottom_radius = RING_RADIUS
	floor_mesh.height = 0.3
	floor_mesh.radial_segments = 8
	var floor_mi := MeshInstance3D.new()
	floor_mi.mesh = floor_mesh
	floor_mi.material_override = floor_mat
	floor_mi.position.y = -0.15
	floor_mi.rotation_degrees.y = 22.5
	add_child(floor_mi)

	# Markazdagi logotip
	var logo := Label3D.new()
	logo.text = "TURON MMA"
	logo.font_size = 160
	logo.pixel_size = 0.005
	logo.modulate = Color(0.75, 0.1, 0.1, 0.85)
	logo.outline_size = 0
	logo.rotation_degrees.x = -90
	logo.position.y = 0.005
	add_child(logo)

	# Ring atrofidagi qorong'i zal
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 60)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.06, 0.06, 0.08)
	ground.material_override = gm
	ground.position.y = -0.3
	add_child(ground)

	# Panjara: ustunlar va to'r
	var post_mat := StandardMaterial3D.new()
	post_mat.albedo_color = Color(0.1, 0.1, 0.1)
	var pad_mat := StandardMaterial3D.new()
	pad_mat.albedo_color = Color(0.7, 0.08, 0.08)
	var fence_mat := StandardMaterial3D.new()
	fence_mat.albedo_color = Color(0.15, 0.15, 0.15, 0.25)
	fence_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	fence_mat.cull_mode = BaseMaterial3D.CULL_DISABLED

	var corner_r := RING_RADIUS
	for i in 8:
		var a := TAU * i / 8.0
		var p := Vector3(cos(a), 0, sin(a)) * corner_r
		var post := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.07
		cyl.bottom_radius = 0.07
		cyl.height = 1.9
		post.mesh = cyl
		post.material_override = post_mat
		post.position = p + Vector3(0, 0.95, 0)
		add_child(post)

		var pad := MeshInstance3D.new()
		var pcyl := CylinderMesh.new()
		pcyl.top_radius = 0.12
		pcyl.bottom_radius = 0.12
		pcyl.height = 0.6
		pad.mesh = pcyl
		pad.material_override = pad_mat
		pad.position = p + Vector3(0, 1.0, 0)
		add_child(pad)

		var b := TAU * (i + 1) / 8.0
		var q := Vector3(cos(b), 0, sin(b)) * corner_r
		var mid := (p + q) / 2.0
		var length := p.distance_to(q)
		var panel := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(length, 1.8, 0.02)
		panel.mesh = box
		panel.material_override = fence_mat
		panel.position = mid + Vector3(0, 0.95, 0)
		panel.look_at_from_position(panel.position, Vector3(0, 0.95, 0), Vector3.UP)
		add_child(panel)

		var rail := MeshInstance3D.new()
		var rbox := BoxMesh.new()
		rbox.size = Vector3(length, 0.1, 0.1)
		rail.mesh = rbox
		rail.material_override = pad_mat
		rail.position = mid + Vector3(0, 1.88, 0)
		rail.look_at_from_position(rail.position, Vector3(0, 1.88, 0), Vector3.UP)
		add_child(rail)


func _spawn_fighters() -> void:
	player = Fighter.new()
	player.name = "Player"
	player.fighter_name = "SIZ"
	player.shorts_color = Color(0.1, 0.35, 0.85)
	player.glove_color = Color(0.85, 0.1, 0.1)
	player.skin_color = Color(0.87, 0.68, 0.53)
	add_child(player)

	bot = Fighter.new()
	bot.name = "Bot"
	bot.fighter_name = "TEMUR \"BO'RI\""
	bot.shorts_color = Color(0.8, 0.1, 0.1)
	bot.glove_color = Color(0.1, 0.1, 0.1)
	bot.skin_color = Color(0.72, 0.53, 0.4)
	add_child(bot)

	player.opponent = bot
	bot.opponent = player
	for f in [player, bot]:
		f.ring_radius = RING_RADIUS - 0.7
		f.hit_landed.connect(_on_hit_landed)
		f.knocked_out.connect(_on_knocked_out)


func _build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 55
	add_child(camera)
	camera.make_current()
	_update_camera(1.0)


# ---------------------------------------------------------------------------
# Raund mantiqi
# ---------------------------------------------------------------------------

func _start_round() -> void:
	_state = MatchState.INTRO
	_state_time = 0.0
	_time_left = ROUND_TIME
	_round_damage = [0.0, 0.0]
	var heal := 0.0 if _round == 1 else 25.0
	player.reset_for_round(Vector3(-START_X, 0, 0), heal)
	bot.reset_for_round(Vector3(START_X, 0, 0), heal)
	player.can_act = false
	bot.can_act = false
	hud.set_round(_round, ROUNDS)
	hud.set_time(_time_left)
	hud.show_message("%d-RAUND" % _round, 1.2)


func _physics_process(delta: float) -> void:
	_state_time += delta
	match _state:
		MatchState.INTRO:
			if _state_time > 1.8:
				_state = MatchState.FIGHT
				_state_time = 0.0
				player.can_act = true
				bot.can_act = true
				hud.show_message("JANG!", 0.5, Color(1, 0.85, 0.2))
		MatchState.FIGHT:
			_time_left -= delta
			hud.set_time(_time_left)
			if _time_left <= 0.0:
				_end_round()
		MatchState.ROUND_END:
			if _state_time > 2.5:
				_round += 1
				if _round > ROUNDS:
					_decision()
				else:
					_start_round()
		MatchState.MATCH_END:
			pass
	hud.update_fighters([player, bot])


func _process(delta: float) -> void:
	_update_camera(delta)


func _end_round() -> void:
	_state = MatchState.ROUND_END
	_state_time = 0.0
	player.can_act = false
	bot.can_act = false
	# 10 balli tizim: raundda ko'proq zarar bergan 10, ikkinchisi 9 oladi.
	var diff: float = _round_damage[0] - _round_damage[1]
	if abs(diff) < 3.0:
		_scores[0] += 10
		_scores[1] += 10
	elif diff > 0:
		_scores[0] += 10
		_scores[1] += 9
	else:
		_scores[0] += 9
		_scores[1] += 10
	hud.show_message("RAUND TUGADI", 1.6)


func _decision() -> void:
	_state = MatchState.MATCH_END
	var text := "HAKAMLAR QARORI\n%d — %d\n\n" % [_scores[0], _scores[1]]
	if _scores[0] > _scores[1]:
		text += "SIZ G'OLIB!"
	elif _scores[0] < _scores[1]:
		text += "%s G'OLIB" % bot.fighter_name
	else:
		text += "DURANG"
	hud.show_end(text)


func _on_knocked_out(f: Fighter) -> void:
	if _state != MatchState.FIGHT:
		return
	_state = MatchState.MATCH_END
	player.can_act = false
	bot.can_act = false
	_winner = bot if f == player else player
	_shake = 0.5
	hud.show_message("NOKAUT!", 1.8, Color(1, 0.2, 0.2))
	var text := ("SIZ NOKAUT BILAN G'OLIB!" if _winner == player
		else "%s NOKAUT BILAN G'OLIB" % bot.fighter_name)
	text += "\n%d-raund, %s" % [_round, _format_time(ROUND_TIME - _time_left)]
	get_tree().create_timer(2.2).timeout.connect(func(): hud.show_end(text))


func _format_time(s: float) -> String:
	var i := int(s)
	return "%d:%02d" % [i / 60, i % 60]


func _on_hit_landed(attacker: Fighter, target: Fighter, damage: float, kind: String) -> void:
	var idx := 0 if attacker == player else 1
	_round_damage[idx] += damage
	var pos := target.global_position + Vector3(0, 1.9, 0)
	match kind:
		"dodge":
			_popup(pos, "QOCHDI", Color(0.4, 1, 0.5))
		"block":
			_popup(pos, "BLOK", Color(0.5, 0.7, 1))
		"guard_break":
			_popup(pos, "HIMOYA SINDI!", Color(1, 0.6, 0.2))
			_shake = max(_shake, 0.2)
		"counter":
			_popup(pos, "KONTR! -%d" % int(round(damage)), Color(1, 0.85, 0.2))
			_shake = max(_shake, 0.3)
		_:
			_popup(pos, "-%d" % int(round(damage)), Color(1, 0.3, 0.3))
			_shake = max(_shake, 0.08 + damage * 0.012)


func _popup(pos: Vector3, text: String, color: Color) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = 64
	l.pixel_size = 0.004
	l.modulate = color
	l.outline_size = 12
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.position = pos + Vector3(randf_range(-0.2, 0.2), 0, 0)
	add_child(l)
	var t := l.create_tween().set_parallel(true)
	t.tween_property(l, "position:y", pos.y + 0.6, 0.8)
	t.tween_property(l, "modulate:a", 0.0, 0.8).set_delay(0.3)
	t.chain().tween_callback(l.queue_free)


func _update_camera(delta: float) -> void:
	# Kamera doim yon tomondan qaraydi: o'yinchi chapda, raqib o'ngda.
	var a := player.global_position
	var b := bot.global_position
	var mid := (a + b) / 2.0
	var d := b - a
	d.y = 0
	d = d.normalized() if d.length() > 0.01 else Vector3.RIGHT
	var forward := Vector3.UP.cross(d)
	var dist := clampf(3.4 + a.distance_to(b) * 0.9, 4.0, 7.0)
	var target_pos := mid - forward * dist + Vector3(0, 1.7, 0)
	# Kamera panjara ichida qolsin, aks holda ustunlar ko'rinishni to'sadi.
	var flat := Vector2(target_pos.x, target_pos.z)
	if flat.length() > CAMERA_MAX_RADIUS:
		flat = flat.normalized() * CAMERA_MAX_RADIUS
		target_pos.x = flat.x
		target_pos.z = flat.y
	var w := clampf(delta * 5.0, 0.0, 1.0)
	camera.global_position = camera.global_position.lerp(target_pos, w)
	var look := mid + Vector3(0, 1.15, 0)
	if _shake > 0.0:
		_shake = max(0.0, _shake - delta * 1.5)
		look += Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * _shake * 0.15
	camera.look_at(look, Vector3.UP)
