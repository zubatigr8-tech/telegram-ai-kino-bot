class_name AIController
extends Node
## Bot jangchini boshqaradi: masofani ushlaydi, kombinatsiyalar uradi,
## raqib zarbasiga blok yoki qochish bilan javob beradi.

const COMBOS := [
	["jab"],
	["jab", "cross"],
	["jab", "jab", "cross"],
	["jab", "cross", "hook"],
	["cross", "hook"],
	["hook", "uppercut"],
	["low_kick"],
	["jab", "low_kick"],
	["high_kick"],
	["jab", "cross", "high_kick"],
]

var fighter: Fighter
## 0.0 — oson, 1.0 — juda qiyin
var difficulty := 0.5

var _think_time := 0.0
var _circle_dir := 1.0
var _combo: Array = []
var _block_time := 0.0
var _last_seen_attack := -1


func _physics_process(delta: float) -> void:
	if fighter == null or fighter.opponent == null:
		return
	if not fighter.can_act:
		fighter.move_input = Vector2.ZERO
		fighter.set_block(false)
		return

	_react_to_attack()

	_block_time -= delta
	fighter.set_block(_block_time > 0.0)

	# Kombo davom etayotgan bo'lsa, keyingi zarbani yuboramiz.
	if not _combo.is_empty() and fighter.state == Fighter.State.IDLE and _block_time <= 0.0:
		fighter.request_attack(_combo.pop_front())

	_think_time -= delta
	if _think_time > 0.0:
		return
	_think_time = randf_range(0.18, 0.45) * (1.3 - difficulty * 0.6)
	_decide()


func _react_to_attack() -> void:
	var opp := fighter.opponent
	if not opp.is_in_windup() or opp.attack_id == _last_seen_attack:
		return
	_last_seen_attack = opp.attack_id
	if fighter.distance_to_opponent() > 1.9 or fighter.state != Fighter.State.IDLE:
		return
	if randf() > 0.2 + 0.5 * difficulty:
		return
	_combo.clear()
	if fighter.stamina > 25.0 and randf() < 0.3:
		fighter.request_dodge()
	else:
		_block_time = randf_range(0.35, 0.6)


func _decide() -> void:
	var dist := fighter.distance_to_opponent()
	var mv := Vector2.ZERO
	if randf() < 0.15:
		_circle_dir = -_circle_dir

	if fighter.stamina < 22.0:
		# Charchagan — orqaga chekinib, nafas rostlaydi.
		mv = Vector2(-0.8, _circle_dir * 0.7)
		if randf() < 0.4:
			_block_time = 0.5
	elif dist > 1.45:
		mv = Vector2(1.0, _circle_dir * 0.3)
	elif dist < 0.95:
		mv = Vector2(-0.6, _circle_dir * 0.4)
	else:
		mv = Vector2(randf_range(-0.2, 0.3), _circle_dir * 0.5)
		if _combo.is_empty() and randf() < 0.45 + 0.35 * difficulty:
			_combo = COMBOS.pick_random().duplicate()
	fighter.move_input = mv
