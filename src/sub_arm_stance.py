# -*- coding: utf-8 -*-
# 移動系ボーン縮尺処理
# 
import logging
import copy
from PyQt5.QtGui import QQuaternion, QVector3D, QVector2D, QMatrix4x4, QVector4D

from VmdWriter import VmdWriter, VmdBoneFrame
from VmdReader import VmdReader
from PmxModel import PmxModel, SizingException
from PmxReader import PmxReader
import utils

logger = logging.getLogger("__main__").getChild(__name__)

def exec(motion, trace_model, replace_model, error_path, error_file_logger):

    if motion.motion_cnt > 0:
        # -----------------------------------------------------------------
        # 腕の角度補正
                    
        # センターから手首までの位置(作成元モデル)
        all_org_wrist_links, _ = trace_model.create_link_2_top_lr("手首")

        # センターから手首までの位置(トレース先モデル)
        all_rep_wrist_links, _ = replace_model.create_link_2_top_lr("手首")
        logger.debug("all_rep_wrist_links: %s", [ "{0}: {1}\n".format(x.name, x.position) for x in all_rep_wrist_links["左"]])    

        all_d_list = [{"肩":"左肩", "腕":"左腕", "ひじ":"左ひじ", "手首":"左手首"}, {"肩":"右肩", "腕":"右腕", "ひじ":"右ひじ", "手首":"右手首"}]
        if set(all_d_list[0].values()).issubset(trace_model.bones) and set(all_d_list[0].values()).issubset(replace_model.bones) and \
            set(all_d_list[1].values()).issubset(trace_model.bones) and set(all_d_list[1].values()).issubset(replace_model.bones):

            # 腕の各パーツの補正角度（キー：ボーン名、値：補正クォータニオン）
            left_arm_stance_qqs = calc_arm_stance(trace_model, all_org_wrist_links, replace_model, all_rep_wrist_links, "左")
            right_arm_stance_qqs = calc_arm_stance(trace_model, all_org_wrist_links, replace_model, all_rep_wrist_links, "右")

            # for lak, lav in left_arm_stance_qqs.items():
            #     logger.debug("lak: %s, lav: %s", lak, lav.toEulerAngles())
            #     logger.debug("lak: %s,lavi: %s", lak, lav.inverted().toEulerAngles())

            for dlist in all_d_list:
                # 方向
                direction = "左" if "左肩" == dlist["肩"] else "右"

                # 方向別
                arm_stance_qqs = left_arm_stance_qqs if direction == "左" else right_arm_stance_qqs

                # # 肩ボーンの入り方はモデルによって異なるため保留
                # if dlist["肩"] in motion.frames:
                #     # 肩
                #     for bf in motion.frames[dlist["肩"]]:
                #         if bf.key == True:
                #             bf.rotation = bf.rotation * arm_stance_qqs["肩"].inverted()
                # if dlist["腕"] in motion.frames:
                #     # 腕
                #     for bf in motion.frames[dlist["腕"]]:
                #         if bf.key == True:
                #             bf.rotation = arm_stance_qqs["肩"] * bf.rotation * arm_stance_qqs["腕"].inverted()

                if dlist["腕"] in motion.frames:
                    # 腕
                    for bf in motion.frames[dlist["腕"]]:
                        if bf.key == True:
                            bf.rotation = bf.rotation * arm_stance_qqs["腕"]

                if dlist["ひじ"] in motion.frames:
                    # ひじ
                    for bf in motion.frames[dlist["ひじ"]]:
                        if bf.key == True:
                            bf.rotation = arm_stance_qqs["腕"].inverted() * bf.rotation * arm_stance_qqs["ひじ"]

                if dlist["手首"] in motion.frames:
                    # 手首
                    for bf in motion.frames[dlist["手首"]]:
                        if bf.key == True:
                            bf.rotation = bf.rotation * arm_stance_qqs["手首"]

    return True


def calc_arm_stance(trace_model, all_org_wrist_links, replace_model, all_replace_wrist_links, direction):
    from_bone = ["肩", "腕", "ひじ", "手首"]
    to_bone = ["腕", "ひじ", "手首", "手先"]
    arm_stance_qqs = {}
    for f, t in zip(from_bone, to_bone):
        org_qq = calc_arm_stance_rotation(trace_model, all_org_wrist_links[direction], f, t, direction)
        rep_qq = calc_arm_stance_rotation(replace_model, all_replace_wrist_links[direction], f, t, direction)

        arm_stance_qqs[f] = rep_qq.inverted() * org_qq

        logger.debug("f: %s, org_qq: %s", f, org_qq.toEulerAngles())
        logger.debug("f: %s, rep_qq: %s", f, rep_qq.toEulerAngles())
        logger.debug("d: %s, f: %s, arm_stance_qqs: %s", direction, f, arm_stance_qqs[f].toEulerAngles())

    return arm_stance_qqs



def calc_arm_stance_rotation(model, wrist_links, fbone, tbone, direction):
    from_pos = QVector3D()
    to_pos = QVector3D()
    tail_pos = QVector3D()

    for fk, fv in enumerate(wrist_links):
        if fv.name.endswith(fbone):
            from_pos = fv.position
            if fv.tail_position != QVector3D:
                # 表示先が相対パスの場合、保持
                tail_pos = fv.tail_position
        if fv.name.endswith(tbone):
            to_pos = fv.position
    
    if to_pos == QVector3D() and tail_pos != QVector3D():
        to_pos = tail_pos
        logger.debug("to_pos 置換: %s", to_pos)

    from_qq = QQuaternion()
    if from_pos != QVector3D and to_pos != QVector3D:
        logger.debug("from_pos: %s", from_pos)        
        logger.debug("to_pos: %s", to_pos)        

        to_pos = to_pos - from_pos
        to_pos.normalize()
        logger.debug("to_pos: %s", to_pos)        

        # 水平からTOボーンまでの回転量
        direction_x = 1 if direction == "左" else -1
        from_qq = QQuaternion.rotationTo(QVector3D(direction_x, 0, 0), to_pos)
        logger.debug("[z] d: %s, fbone: %s, from_qq: %s", direction, fbone, from_qq.toEulerAngles())

    return from_qq