import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Flip } from "gsap/Flip";
import { CustomEase } from "gsap/CustomEase";
import { ScrambleTextPlugin } from "gsap/ScrambleTextPlugin";

gsap.registerPlugin(
  useGSAP,
  Flip,
  CustomEase,
  ScrambleTextPlugin,
);

CustomEase.create("interface", "0.22, 1, 0.36, 1");
CustomEase.create("reveal", "0.16, 1, 0.3, 1");
CustomEase.create("impact", "0.34, 1.56, 0.64, 1");

export {
  gsap,
  useGSAP,
  Flip,
  CustomEase,
  ScrambleTextPlugin,
};
