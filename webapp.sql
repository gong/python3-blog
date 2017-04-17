/*
Navicat MySQL Data Transfer

Source Server         : localhost_3306
Source Server Version : 50621
Source Host           : 127.0.0.1:3306
Source Database       : webapp

Target Server Type    : MYSQL
Target Server Version : 50621
File Encoding         : 65001

Date: 2017-04-16 20:38:11
*/

SET FOREIGN_KEY_CHECKS=0;

-- ----------------------------
-- Table structure for blogs
-- ----------------------------
DROP TABLE IF EXISTS `blogs`;
CREATE TABLE `blogs` (
  `id` varchar(50) NOT NULL,
  `user_id` varchar(50) NOT NULL,
  `user_name` varchar(50) NOT NULL,
  `user_image` varchar(500) NOT NULL,
  `name` varchar(50) NOT NULL,
  `summary` varchar(200) NOT NULL,
  `content` mediumtext NOT NULL,
  `created_at` double NOT NULL,
  `blogtag_id` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for blogtags
-- ----------------------------
DROP TABLE IF EXISTS `blogtags`;
CREATE TABLE `blogtags` (
  `id` varchar(50) NOT NULL,
  `name` varchar(50) NOT NULL,
  `created_at` varchar(255) NOT NULL,
  `remarks` mediumtext
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for comments
-- ----------------------------
DROP TABLE IF EXISTS `comments`;
CREATE TABLE `comments` (
  `id` varchar(50) NOT NULL,
  `blog_id` varchar(50) NOT NULL,
  `user_id` varchar(50) NOT NULL,
  `user_name` varchar(50) NOT NULL,
  `user_image` varchar(500) NOT NULL,
  `content` mediumtext NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` varchar(50) NOT NULL,
  `email` varchar(50) NOT NULL,
  `passwd` varchar(50) NOT NULL,
  `admin` tinyint(1) DEFAULT NULL,
  `name` varchar(50) NOT NULL,
  `image` varchar(500) NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_email` (`email`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
