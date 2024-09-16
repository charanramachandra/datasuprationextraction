-- phpMyAdmin SQL Dump
-- version 5.0.3
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Sep 11, 2024 at 06:24 AM
-- Server version: 10.4.14-MariaDB
-- PHP Version: 7.4.11

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `katachinew`
--

-- --------------------------------------------------------

--
-- Table structure for table `admins`
--

CREATE TABLE `admins` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `plaintext_password` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `admins`
--

INSERT INTO `admins` (`id`, `username`, `password`, `created_at`, `plaintext_password`) VALUES
(3, 'rama', 'sha256$j0NZsJUjLwRTHwLS$63e8267b2b8d0feb2645d571e9c9867fe96af1895d5cc194d5e90cc4391268d2', '2024-09-11 03:51:46', 'rama08');

-- --------------------------------------------------------

--
-- Table structure for table `final_data`
--

CREATE TABLE `final_data` (
  `id` int(11) NOT NULL,
  `user_id` varchar(50) DEFAULT NULL,
  `image_name` varchar(50) DEFAULT NULL,
  `todays_work` varchar(50) DEFAULT NULL,
  `address` varchar(50) DEFAULT NULL,
  `company_name` varchar(50) DEFAULT NULL,
  `company_owner_name` varchar(50) DEFAULT NULL,
  `telephone_number` varchar(50) DEFAULT NULL,
  `company_name2` varchar(150) DEFAULT NULL,
  `company_address2` varchar(50) DEFAULT NULL,
  `code_number` varchar(50) DEFAULT NULL,
  `telephone_number2` varchar(50) DEFAULT NULL,
  `username` varchar(50) DEFAULT NULL,
  `R1_record_number` varchar(50) DEFAULT NULL,
  `R1_type_code` varchar(50) DEFAULT NULL,
  `R1_garbage_weight` varchar(50) DEFAULT NULL,
  `R1_number_of_items` varchar(50) DEFAULT NULL,
  `R1_registered_number` varchar(50) DEFAULT NULL,
  `R1_company_name` varchar(150) DEFAULT NULL,
  `R1_company_address` varchar(50) DEFAULT NULL,
  `R1_address_code` varchar(50) DEFAULT NULL,
  `R1_number_of_company_items` varchar(50) DEFAULT NULL,
  `R1_company_item_code` varchar(50) DEFAULT NULL,
  `R1_company_name_2` varchar(50) DEFAULT NULL,
  `R1_company_address2` varchar(50) DEFAULT NULL,
  `R1_address_code2` varchar(50) DEFAULT NULL,
  `R2_record_number` varchar(50) DEFAULT NULL,
  `R2_type_code` varchar(50) DEFAULT NULL,
  `R2_garbage_weight` varchar(50) DEFAULT NULL,
  `R2_number_of_items` varchar(50) DEFAULT NULL,
  `R2_registered_number` varchar(50) DEFAULT NULL,
  `R2_company_name` varchar(50) DEFAULT NULL,
  `R2_company_address` varchar(50) DEFAULT NULL,
  `R2_address_code` varchar(50) DEFAULT NULL,
  `R2_number_of_company_items` varchar(50) DEFAULT NULL,
  `R2_company_item_code` varchar(50) DEFAULT NULL,
  `R2_company_name_2` varchar(50) DEFAULT NULL,
  `R2_company_address2` varchar(50) DEFAULT NULL,
  `R2_address_code2` varchar(50) DEFAULT NULL,
  `R3_record_number` varchar(50) DEFAULT NULL,
  `R3_type_code` varchar(50) DEFAULT NULL,
  `R3_garbage_weight` varchar(50) DEFAULT NULL,
  `R3_number_of_items` varchar(50) DEFAULT NULL,
  `R3_registered_number` varchar(50) DEFAULT NULL,
  `R3_company_name` varchar(50) DEFAULT NULL,
  `R3_company_address` varchar(50) DEFAULT NULL,
  `R3_address_code` varchar(50) DEFAULT NULL,
  `R3_number_of_company_items` varchar(50) DEFAULT NULL,
  `R3_company_item_code` varchar(50) DEFAULT NULL,
  `R3_company_name_2` varchar(150) DEFAULT NULL,
  `R3_company_address2` varchar(50) DEFAULT NULL,
  `R3_address_code2` varchar(50) DEFAULT NULL,
  `R4_record_number` varchar(50) DEFAULT NULL,
  `R4_type_code` varchar(50) DEFAULT NULL,
  `R4_garbage_weight` varchar(50) DEFAULT NULL,
  `R4_number_of_items` varchar(50) DEFAULT NULL,
  `R4_registered_number` varchar(50) DEFAULT NULL,
  `R4_company_name` varchar(50) DEFAULT NULL,
  `R4_company_address` varchar(50) DEFAULT NULL,
  `R4_address_code` varchar(50) DEFAULT NULL,
  `R4_number_of_company_items` varchar(50) DEFAULT NULL,
  `R4_company_item_code` varchar(50) DEFAULT NULL,
  `R4_company_name_2` varchar(150) DEFAULT NULL,
  `R4_company_address2` varchar(50) DEFAULT NULL,
  `R4_address_code2` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `final_data`
--

INSERT INTO `final_data` (`id`, `user_id`, `image_name`, `todays_work`, `address`, `company_name`, `company_owner_name`, `telephone_number`, `company_name2`, `company_address2`, `code_number`, `telephone_number2`, `username`, `R1_record_number`, `R1_type_code`, `R1_garbage_weight`, `R1_number_of_items`, `R1_registered_number`, `R1_company_name`, `R1_company_address`, `R1_address_code`, `R1_number_of_company_items`, `R1_company_item_code`, `R1_company_name_2`, `R1_company_address2`, `R1_address_code2`, `R2_record_number`, `R2_type_code`, `R2_garbage_weight`, `R2_number_of_items`, `R2_registered_number`, `R2_company_name`, `R2_company_address`, `R2_address_code`, `R2_number_of_company_items`, `R2_company_item_code`, `R2_company_name_2`, `R2_company_address2`, `R2_address_code2`, `R3_record_number`, `R3_type_code`, `R3_garbage_weight`, `R3_number_of_items`, `R3_registered_number`, `R3_company_name`, `R3_company_address`, `R3_address_code`, `R3_number_of_company_items`, `R3_company_item_code`, `R3_company_name_2`, `R3_company_address2`, `R3_address_code2`, `R4_record_number`, `R4_type_code`, `R4_garbage_weight`, `R4_number_of_items`, `R4_registered_number`, `R4_company_name`, `R4_company_address`, `R4_address_code`, `R4_number_of_company_items`, `R4_company_item_code`, `R4_company_name_2`, `R4_company_address2`, `R4_address_code2`) VALUES
(8, NULL, '00450.jpg', NULL, '東京都千代田区神田錦町1-1-1 帝都神田ビル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成', '03-4360-3558', 'ヨドバシ梅田タワー', '〒530-0011 大阪市北区大深町1-1', '92', '06-6359-2018', NULL, '1', '0200', '15.07', '11', '02700001251 6610010259 02700164034-04000164034', '藤野興業(株) アスト(株) 海栄(株)', '大阪市大正区平尾1-4-20 北九州市若松区響町1-1-8', '27100 40100', '07620002851', '201', '(株)サニックス', '広島県呉市町ワラヒノ山12528番外', '34202', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
(16, NULL, '00451.jpg', NULL, '', 'kingkong', 'ito', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `skipped_sections`
--

CREATE TABLE `skipped_sections` (
  `image_name` varchar(255) DEFAULT NULL,
  `skipped_section` varchar(255) DEFAULT NULL,
  `Reasons` varchar(225) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `skipped_sections`
--

INSERT INTO `skipped_sections` (`image_name`, `skipped_section`, `Reasons`) VALUES
('00452.jpg', 'Phone Number', 'cant read it'),
('00453.jpg', 'Company Name 2', 'cant read it'),
('00454.jpg', 'Code Number', 'something unusuall has be disblayed');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `plaintext_password` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `username`, `password`, `created_at`, `plaintext_password`) VALUES
(3, 'rama', 'sha256$yuqiQ4DvQd0X6LBn$366701366f8301afc89eb02196c73000cd467aeab805e810c83127dfb65d1e74', '2024-09-04 08:45:25', 'rama08'),
(4, 'charan', 'sha256$JyDmYmfUoc8zVhyl$ad687d94a697b1a76ad68aa3ee5974b12ffba296c931977df9d10d1c1e0e4256', '2024-09-11 03:51:14', 'charan08'),
(5, 'testuser', 'sha256$P4DIlS49psxx8njV$f50a918cfd1eb14a780fbf11b8cc983948b72b668850998b999d8026f205ef7d', '2024-09-04 07:45:27', 'charan08');

-- --------------------------------------------------------

--
-- Table structure for table `user_images`
--

CREATE TABLE `user_images` (
  `id` int(11) NOT NULL,
  `user_id` varchar(255) NOT NULL,
  `image_name` varchar(255) NOT NULL,
  `address` varchar(255) NOT NULL,
  `company_name` varchar(255) NOT NULL,
  `company_owner_name` varchar(255) NOT NULL,
  `telephone_number` varchar(255) NOT NULL,
  `company_name2` varchar(255) NOT NULL,
  `company_address2` varchar(255) NOT NULL,
  `code_number` varchar(255) NOT NULL,
  `telephone_number2` varchar(255) NOT NULL,
  `username` varchar(255) NOT NULL,
  `R1_record_number` varchar(50) NOT NULL,
  `R1_type_code` varchar(50) NOT NULL,
  `R1_garbage_weight` varchar(50) NOT NULL,
  `R1_number_of_items` varchar(50) NOT NULL,
  `R1_registered_number` varchar(50) NOT NULL,
  `R1_company_name` varchar(100) NOT NULL,
  `R1_company_address` varchar(255) NOT NULL,
  `R1_address_code` varchar(50) NOT NULL,
  `R1_number_of_company_items` varchar(50) NOT NULL,
  `R1_company_item_code` varchar(50) NOT NULL,
  `R1_company_name_2` varchar(100) NOT NULL,
  `R2_record_number` varchar(50) NOT NULL,
  `R2_type_code` varchar(50) NOT NULL,
  `R2_garbage_weight` varchar(50) NOT NULL,
  `R2_number_of_items` varchar(50) NOT NULL,
  `R2_registered_number` varchar(50) NOT NULL,
  `R2_company_name` varchar(100) NOT NULL,
  `R2_company_address` varchar(255) NOT NULL,
  `R2_address_code` varchar(50) NOT NULL,
  `R2_number_of_company_items` varchar(50) NOT NULL,
  `R2_company_item_code` varchar(50) NOT NULL,
  `R2_company_name_2` varchar(100) NOT NULL,
  `R3_record_number` varchar(50) NOT NULL,
  `R3_type_code` varchar(50) NOT NULL,
  `R3_garbage_weight` varchar(50) NOT NULL,
  `R3_number_of_items` varchar(50) NOT NULL,
  `R3_registered_number` varchar(50) NOT NULL,
  `R3_company_name` varchar(100) NOT NULL,
  `R3_company_address` varchar(255) NOT NULL,
  `R3_address_code` varchar(50) NOT NULL,
  `R3_number_of_company_items` varchar(50) NOT NULL,
  `R3_company_item_code` varchar(50) NOT NULL,
  `R3_company_name_2` varchar(100) NOT NULL,
  `R4_record_number` varchar(50) NOT NULL,
  `R4_type_code` varchar(50) NOT NULL,
  `R4_garbage_weight` varchar(50) NOT NULL,
  `R4_number_of_items` varchar(50) NOT NULL,
  `R4_registered_number` varchar(50) NOT NULL,
  `R4_company_name` varchar(100) NOT NULL,
  `R4_company_address` varchar(255) NOT NULL,
  `R4_address_code` varchar(50) NOT NULL,
  `R4_number_of_company_items` varchar(50) NOT NULL,
  `R4_company_item_code` varchar(50) NOT NULL,
  `R4_company_name_2` varchar(100) NOT NULL,
  `todays_work` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `R1_company_address2` varchar(255) NOT NULL,
  `R1_address_code2` varchar(100) NOT NULL,
  `R2_company_address2` varchar(255) NOT NULL,
  `R2_address_code2` varchar(100) NOT NULL,
  `R3_company_address2` varchar(255) NOT NULL,
  `R3_address_code2` varchar(100) NOT NULL,
  `R4_company_address2` varchar(255) NOT NULL,
  `R4_address_code2` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `user_images`
--

INSERT INTO `user_images` (`id`, `user_id`, `image_name`, `address`, `company_name`, `company_owner_name`, `telephone_number`, `company_name2`, `company_address2`, `code_number`, `telephone_number2`, `username`, `R1_record_number`, `R1_type_code`, `R1_garbage_weight`, `R1_number_of_items`, `R1_registered_number`, `R1_company_name`, `R1_company_address`, `R1_address_code`, `R1_number_of_company_items`, `R1_company_item_code`, `R1_company_name_2`, `R2_record_number`, `R2_type_code`, `R2_garbage_weight`, `R2_number_of_items`, `R2_registered_number`, `R2_company_name`, `R2_company_address`, `R2_address_code`, `R2_number_of_company_items`, `R2_company_item_code`, `R2_company_name_2`, `R3_record_number`, `R3_type_code`, `R3_garbage_weight`, `R3_number_of_items`, `R3_registered_number`, `R3_company_name`, `R3_company_address`, `R3_address_code`, `R3_number_of_company_items`, `R3_company_item_code`, `R3_company_name_2`, `R4_record_number`, `R4_type_code`, `R4_garbage_weight`, `R4_number_of_items`, `R4_registered_number`, `R4_company_name`, `R4_company_address`, `R4_address_code`, `R4_number_of_company_items`, `R4_company_item_code`, `R4_company_name_2`, `todays_work`, `R1_company_address2`, `R1_address_code2`, `R2_company_address2`, `R2_address_code2`, `R3_company_address2`, `R3_address_code2`, `R4_company_address2`, `R4_address_code2`) VALUES
(35, '4', '00448.jpg', '東京都千代田区外神田四丁目14番1号', 'イー・アンド・イーソリューションズ株式会社', '代表取締役 川上 智', '03-6328-0120', 'エムエムステンレスリサイクル株式会社内工事場所', '大阪市西淀川区御幣島5丁目15番17号', '23', '06-6473-2111', 'charan', '1', '1321', '1.55', '1', '6610190966', '株式会社TOC', '大阪府大阪市西成区津守3丁目8-80', '27100', '6620190966', '207', '株式会社TOC', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '', '', '', '', '', '', '', '', '', '', '', '2024-09-03 05:26:06', '大阪府大阪市西成区津守3丁目8-80', '27100', ' ', ' ', ' ', ' ', '', ''),
(36, '4', '00449.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成', '03-4360-3558', '日新建物船場ビル', '〒541-0056 大阪市中央区久太郎町3-1-30', '92', '06-6252-1405', 'charan', '1', '0200', '1.0', '2', '02700067111', 'クリーン関西 株式会社', '大阪府大阪市大正区平尾1丁目4-20', '27100', ' ', ' ', ' ', '1', ' ', ' ', ' ', '6610010259', 'アスト株式会社', '大阪府大阪市大正区平尾1丁目4-20', '27100', ' ', ' ', ' ', '1', ' ', ' ', ' ', '02700164034', '海栄株式会社', '福岡県北九州市若松区響町1-1-8', '40100', '07620002851', '201', '株式会社サニックス', '', '', '', '', '', '', '', '', '', '', '', '2024-09-03 05:26:11', ' ', ' ', ' ', ' ', ' ', ' ', '', ''),
(37, '3', '00448.jpg', '東京都千代田区外神田四丁目14番1号1', 'イー・アンド・イーソリューションズ株式会社', '代表取締役 川上 智', '03-6328-0120', 'エムエムステンレスリサイクル株式会社内工事場所', '大阪市西淀川区御幣島5丁目15番17号', '23', '06-6473-2111', 'rama', '1', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-02 00:20:05', '', '', '', '', '', '', '', ''),
(38, '3', '00449.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビ2ル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成', '03-4360-3558', '日新建物船場ビル', '〒541-0056 大阪市中央区久太郎町3-1-30', '92', '06-6252-1405', 'rama', '1', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-02 00:20:08', '', '', '', '', '', '', '', ''),
(60, '4', '00450.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成', '03-4360-3558', 'ヨドバシ梅田タワー', '〒530-0011 大阪市北区大深町1-1', '92', '06-6359-2018', 'charan', '1', '0200', '15.07', '11', '02700001251 6610010259 02700164034-04000164034', '藤野興業(株) アスト(株) 海栄(株)', '大阪市大正区平尾1-4-20 北九州市若松区響町1-1-8', '27100 40100', '07620002851', '201', '(株)サニックス', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-04 04:41:04', '広島県呉市町ワラヒノ山12528番外', '34202', '', '', '', '', '', ''),
(61, '4', '00450_-_Copy.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル2', 'イオンディライト株式会社2', '代表取締役社長 濱田 和成', '03-4360-35588', 'ヨドバシ梅田タワー2', '〒530-0011 大阪市北区大深町1-12', '922', '06-6359-20180', 'charan', '11', '02000', '15.077', '112', '02700001251 6610010259 02700164034-0400016403455', '藤野興業(株) アスト(株) 海栄(株)han', '大阪市大正区平尾1-4-20 北九州市若松区響町1-1-8コー', '27100 401000', '076200028512', '2011', '(株)サニックス広島県呉市', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-04 04:41:10', '広島県呉市町ワラヒノ山12528番外広島県', '342022', '', '', '', '', '', ''),
(62, '3', '00450.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成', '03-4360-3558', 'ヨドバシ梅田タワー', '〒530-0011 大阪市北区大深町1-1', '92', '06-6359-2018', 'rama', '1', '0200', '15.07', '11', '02700001251 6610010259 02700164034-04000164034', ' 藤野興業(株) アスト(株) 海栄(株)', '大阪市大正区平尾1-4-20 北九州市若松区響町1-1-8', '27100 40100', '07620002851', '201', '(株)サニックス', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-04 04:30:47', '広島県呉市町ワラヒノ山12528番外', '34202', '', '', '', '', '', ''),
(63, '3', '00450_-_Copy.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', 'イオンディライト株式会社', '代表取締役社長 濱田 和成2', '03-4360-3558', 'ヨドバシ梅田タワー', '〒530-0011 大阪市北区大深町1-1', '92', '06-6359-2018', 'rama', '1', '0200', '15.07', '11', '02700001251 6610010259 02700164034-04000164034', '藤野興業(株) アスト(株) 海栄(株)', '大阪市大正区平尾1-4-20 北九州市若松区響町1-1-8', '27100 40100', '07620002851', '201', '(株)サニックス', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-04 04:30:54', '広島県呉市町ワラヒノ山12528番外', '34202', '', '', '', '', '', ''),
(64, '4', '00451.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', '', '', '', '', '', '', '', 'charan', '', '', '', '', '', '株式会社 国中環境開発', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-05 05:19:30', '', '', '', '', '', '', '', ''),
(65, '4', '00453.jpg', '東京都千代田区神田錦町1-2-3 帝都神田ビル', '', '', '', '', '', '', '', 'charan', '', '', '', '', '', 'サステナブルジャパン株式会社', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-05 05:19:53', '', '', '', '', '', '', '', ''),
(66, '3', '00451.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', '', '', '', '', '', '', '', 'rama', '', '', '', '', '', '株式会社 国中環境開発', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-05 05:19:36', '', '', '', '', '', '', '', ''),
(67, '3', '00453.jpg', '東京都千代田区神田錦町1-1-1 帝都神田ビル', '', '', '', '', '', '', '', 'rama', '', '', '', '', '', 'サステナブル\n| ジャパン株式会\n|社', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '2024-09-05 05:19:56', '', '', '', '', '', '', '', '');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admins`
--
ALTER TABLE `admins`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `final_data`
--
ALTER TABLE `final_data`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `user_images`
--
ALTER TABLE `user_images`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admins`
--
ALTER TABLE `admins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `final_data`
--
ALTER TABLE `final_data`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=17;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `user_images`
--
ALTER TABLE `user_images`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=68;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
