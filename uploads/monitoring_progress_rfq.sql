-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Nov 05, 2026 at 03:57 AM
-- Server version: 10.4.32-MariaDB-log
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `monitoring progress rfq`
--

-- --------------------------------------------------------

--
-- Table structure for table `customers`
--

CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `customers`
--

INSERT INTO `customers` (`id`, `name`) VALUES
(6, 'PT TMMIN');

-- --------------------------------------------------------

--
-- Table structure for table `management_judgements`
--

CREATE TABLE `management_judgements` (
  `id` int(11) NOT NULL,
  `jenis` varchar(50) NOT NULL,
  `customer` varchar(255) DEFAULT '',
  `commodity` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `keputusan` varchar(50) NOT NULL,
  `catatan` text NOT NULL,
  `author` varchar(100) NOT NULL,
  `recipient_divisions` varchar(255) DEFAULT '',
  `email_sent` tinyint(4) DEFAULT 0,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `model_partlists`
--

CREATE TABLE `model_partlists` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `partlist_status` varchar(30) DEFAULT 'Open',
  `partlist_done` int(11) DEFAULT 0,
  `partlist_total` int(11) DEFAULT 1,
  `partlist_note` text DEFAULT NULL,
  `created_at` varchar(30) DEFAULT '',
  `partlist_saved` int(11) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `model_partlists`
--

INSERT INTO `model_partlists` (`id`, `customer_id`, `model_name`, `category`, `year`, `partlist_status`, `partlist_done`, `partlist_total`, `partlist_note`, `created_at`, `partlist_saved`) VALUES
(642, 6, '883D', 'Chassis', 2026, 'Open', 0, 0, NULL, '03-11-2026 08:45', 0),
(644, 6, '111w', 'Chassis', 2026, 'Open', 0, 0, NULL, '03-11-2026 12:48', 0),
(655, 6, 'ddd', 'Chassis', 2026, 'Open', 0, 0, NULL, '05-11-2026 08:45', 0);

-- --------------------------------------------------------

--
-- Table structure for table `model_partlist_files`
--

CREATE TABLE `model_partlist_files` (
  `id` int(11) NOT NULL,
  `model_partlist_id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `approval_status` varchar(30) DEFAULT 'Belum Approval',
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `notes`
--

CREATE TABLE `notes` (
  `id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `author` varchar(100) NOT NULL,
  `text` text NOT NULL,
  `created_at` varchar(30) NOT NULL,
  `attachment_filename` varchar(255) DEFAULT '',
  `attachment_stored_filename` varchar(255) DEFAULT '',
  `recipient_divisions` text DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `parts`
--

CREATE TABLE `parts` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `month` varchar(20) NOT NULL,
  `part_no` varchar(100) NOT NULL,
  `due_date` varchar(10) DEFAULT '',
  `redraw_status` varchar(30) DEFAULT 'Open',
  `redraw_done` int(11) DEFAULT 0,
  `redraw_total` int(11) DEFAULT 1,
  `finish_good` varchar(50) DEFAULT '',
  `komponen` varchar(50) DEFAULT '',
  `drawing_tooling` varchar(50) DEFAULT '',
  `drawing_pipa` varchar(50) DEFAULT '',
  `redraw_note` text DEFAULT NULL,
  `review_status` varchar(30) DEFAULT 'Open',
  `review_done` int(11) DEFAULT 0,
  `review_total` int(11) DEFAULT 1,
  `partlist_status` varchar(30) DEFAULT 'Open',
  `partlist_done` int(11) DEFAULT 0,
  `partlist_total` int(11) DEFAULT 1,
  `partlist_note` text DEFAULT NULL,
  `quick_note` text DEFAULT NULL,
  `kondisi` varchar(20) DEFAULT '',
  `go_decision` varchar(10) DEFAULT '',
  `redraw_saved` int(11) NOT NULL DEFAULT 0,
  `review_saved` int(11) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `parts`
--

INSERT INTO `parts` (`id`, `customer_id`, `model_name`, `category`, `year`, `month`, `part_no`, `due_date`, `redraw_status`, `redraw_done`, `redraw_total`, `finish_good`, `komponen`, `drawing_tooling`, `drawing_pipa`, `redraw_note`, `review_status`, `review_done`, `review_total`, `partlist_status`, `partlist_done`, `partlist_total`, `partlist_note`, `quick_note`, `kondisi`, `go_decision`, `redraw_saved`, `review_saved`) VALUES
(24, 6, '883D', 'Chassis', 2026, 'November', '22q', '', 'Close', 1, 1, '1', '0', '0', '0', '', 'Open', 0, 0, 'Open', 0, 1, NULL, NULL, 'F', '', 1, 0),
(25, 6, '111w', 'Chassis', 2026, 'November', '2222f', '2026-11-04', 'Close', 0, 0, '0', '0', '0', '0', '', 'Close', 1, 1, 'Open', 0, 1, NULL, NULL, 'A', '', 1, 1),
(26, 6, 'ddd', 'Chassis', 2026, 'November', 'qqqq', '2026-11-06', 'Open', 0, 0, '', '', '', '', NULL, 'Open', 0, 0, 'Open', 0, 1, NULL, NULL, 'A', '', 0, 0);

-- --------------------------------------------------------

--
-- Table structure for table `redraw_files`
--

CREATE TABLE `redraw_files` (
  `id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `approval_status` varchar(30) DEFAULT 'Belum Approval',
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL,
  `progress_type` varchar(50) DEFAULT 'Finish Good',
  `display_filename` varchar(255) DEFAULT 'Finish Good'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `redraw_files`
--

INSERT INTO `redraw_files` (`id`, `part_id`, `original_filename`, `stored_filename`, `approval_status`, `uploaded_by`, `divisi`, `created_at`, `progress_type`, `display_filename`) VALUES
(22, 25, 'Template_Laporan_EAS_Big_Data.pdf', '114557f2b76e4a82ad05c06ba3d7f78f_Template_Laporan_EAS_Big_Data.pdf', 'Sudah Approval', 'Kia', 'Engineer', '03-11-2026 12:50', 'Drawing Review', 'Drawing Review'),
(23, 24, 'Essay_tugas_1.docx', '36a8ae430b7f4f40a05e419556b368b2_Essay_tugas_1.docx', 'Sudah Approval', 'Kia', 'Engineer', '05-11-2026 08:44', 'Finish Good', 'Finish Good');

-- --------------------------------------------------------

--
-- Table structure for table `rfq_notes`
--

CREATE TABLE `rfq_notes` (
  `id` int(11) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `author` varchar(100) NOT NULL,
  `customer` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `category` varchar(50) DEFAULT '',
  `text` text NOT NULL,
  `recipient_divisions` varchar(255) DEFAULT '',
  `email_sent` tinyint(4) DEFAULT 0,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `submissions`
--

CREATE TABLE `submissions` (
  `id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `customer` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `category` varchar(50) DEFAULT 'Chasis',
  `year` int(11) DEFAULT NULL,
  `kondisi` varchar(20) DEFAULT '',
  `due_date` varchar(10) DEFAULT '',
  `part_id` int(11) DEFAULT NULL,
  `item_name` varchar(255) DEFAULT '',
  `included_items` text DEFAULT NULL,
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL,
  `marketing_note` text NOT NULL,
  `note_target_divisions` text DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `submissions`
--

INSERT INTO `submissions` (`id`, `original_filename`, `stored_filename`, `description`, `customer`, `model_name`, `partnumber`, `category`, `year`, `kondisi`, `due_date`, `part_id`, `item_name`, `included_items`, `uploaded_by`, `divisi`, `created_at`, `marketing_note`, `note_target_divisions`) VALUES
(27, 'titanic.zip', 'd3b7ef1b4c9a4013bb13efd824675f29_titanic.zip', '', 'PT TMMIN', '883D', '22q', 'Chassis', 2026, 'F', '', 24, '', 'Volume / Year; Current Process; Sample Produk', 'ghaly', 'Marketing', '03-11-2026 08:45', '', 'Engineer'),
(28, 'titanic.zip', '2eee0f9f2f1a4908a10f891c6cdc1f5b_titanic.zip', '', 'PT TMMIN', '111w', '2222f', 'Chassis', 2026, 'A', '2026-11-04', 25, '', 'Drawing 2D Customer (Note pada Drawing, Appearance check, Material, Surface treatment dll); Drawing 3D Customer; Technical Standard Customer; Volume / Year; Customer current; Current Process', 'ghaly', 'Marketing', '03-11-2026 12:48', '', 'Engineer'),
(29, 'archive.zip', 'f0d03fb8b9e249f6ad5a051a12514157_archive.zip', '', 'PT TMMIN', 'ddd', 'qqqq', 'Chassis', 2026, 'A', '2026-11-06', 26, '', 'Drawing 2D Customer (Note pada Drawing, Appearance check, Material, Surface treatment dll); Drawing 3D Customer; Technical Standard Customer; Volume / Year; Customer current; Current Process', 'ghaly', 'Marketing', '05-11-2026 08:45', '', 'Engineer');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `email` varchar(255) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `username`, `password`, `divisi`, `email`) VALUES
(233, 'Kia', 'scrypt:32768:8:1$CGcIOJBlHhQWpxna$8cbc6be9c5fde1a8c691fc640be31aa570a0deb7e5dcdc365228ebdf0637f28aadf1386cb0145549e9e015e6f1c4f45e08558ede7a1d59b93f46222df9207824', 'Engineer', 'hizkiasamhanrezayoshi@gmail.com'),
(252, 'piak', 'scrypt:32768:8:1$te6cT2R9AefcsN0v$7353e3dec749e37a20f439e3be89c29179cc3c2bc49f21918e09d041f6766fa085252acca552712b71d6ecea2e88e7879c5205d558f77f02169e6e4c7567b2b5', 'Engineer', 'najwa8379@sma.belajar.id'),
(546, 'naw', 'scrypt:32768:8:1$1y2WN0UBBmdctvUu$6fc14ffc76be39c5048789012d71cd096e76fccba4f8cf480cf913ae492593036a89a041accd5806dbc61a7569839529f40965da1af7a9f5f9257308714cce0c', 'Purchasing', 'nawwwsfyyy@gmail.com'),
(547, 'sofi', 'scrypt:32768:8:1$sqxVlHERSG7ReV7B$1cfa5bc9aad2d0ea3d181162326084b2c7e4dcb99cac849e7cb332fc4d2df3de92be9b13e80197ede1f91d5e6bea104c61026bb4d86044073f603090925086a8', 'Purchasing', 'najwasofi888@gmail.com'),
(548, 'ghaly', 'scrypt:32768:8:1$aCCyEhOLYorZnvJF$d60dfc9b195518b8a7e2502a9cd14fb871047af657375518e8250adccdb6cde0129fa8efac6eba62697386b52fd9359b0100924995c1a62d4ebd34becaeaefd6', 'Marketing', 'ghalyleo123@gmail.com'),
(549, 'management1', 'scrypt:32768:8:1$d0Kf8Dmjkvix8DrN$0f6e40395dbe37ee8f8956a935edf7f18f404f2c561d960257f4e943a71daa453601eef7a5b18aeea2606560eff90027c5d447352b04b1412fb0f5aeb3915b7f', 'Management', ''),
(582, 'admin', 'scrypt:32768:8:1$8daEXX86tHvLSBHQ$3f2b43d2010669214ab94a96d92e6673f77ddf4c5bd565c7b2ed0047eb74d61d002aa4f5a7669152e1f6cffcde2d184d2e6f61d047cfa952a6f5cc813786cb20', 'Admin', ''),
(672, 'test1', 'scrypt:32768:8:1$E9qY4RRhJwY6y7tx$874d057e2cb9ac958ae986fed969c7e979c474440552425ba49e70b045643af8c4fb86950cb35731c5f23713a80347d204d15b076d0681f6856faa1e47cb0c2c', 'Engineer', 'test@mail.com');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `customers`
--
ALTER TABLE `customers`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_customer_name` (`name`);

--
-- Indexes for table `management_judgements`
--
ALTER TABLE `management_judgements`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `model_partlists`
--
ALTER TABLE `model_partlists`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_model_partlist` (`customer_id`,`model_name`,`category`,`year`),
  ADD KEY `idx_model_partlists_customer` (`customer_id`);

--
-- Indexes for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_model_partlist_files_model` (`model_partlist_id`);

--
-- Indexes for table `notes`
--
ALTER TABLE `notes`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_notes_part` (`part_id`);

--
-- Indexes for table `parts`
--
ALTER TABLE `parts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_parts_customer` (`customer_id`);

--
-- Indexes for table `redraw_files`
--
ALTER TABLE `redraw_files`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_redraw_files_part` (`part_id`);

--
-- Indexes for table `rfq_notes`
--
ALTER TABLE `rfq_notes`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `submissions`
--
ALTER TABLE `submissions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_submissions_part` (`part_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_user_divisi` (`username`,`divisi`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `customers`
--
ALTER TABLE `customers`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `management_judgements`
--
ALTER TABLE `management_judgements`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `model_partlists`
--
ALTER TABLE `model_partlists`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=660;

--
-- AUTO_INCREMENT for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT for table `notes`
--
ALTER TABLE `notes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `parts`
--
ALTER TABLE `parts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=27;

--
-- AUTO_INCREMENT for table `redraw_files`
--
ALTER TABLE `redraw_files`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=24;

--
-- AUTO_INCREMENT for table `rfq_notes`
--
ALTER TABLE `rfq_notes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT for table `submissions`
--
ALTER TABLE `submissions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=30;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=705;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `model_partlists`
--
ALTER TABLE `model_partlists`
  ADD CONSTRAINT `fk_model_partlists_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  ADD CONSTRAINT `fk_model_partlist_files_model` FOREIGN KEY (`model_partlist_id`) REFERENCES `model_partlists` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `notes`
--
ALTER TABLE `notes`
  ADD CONSTRAINT `fk_notes_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `parts`
--
ALTER TABLE `parts`
  ADD CONSTRAINT `fk_parts_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `redraw_files`
--
ALTER TABLE `redraw_files`
  ADD CONSTRAINT `fk_redraw_files_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `submissions`
--
ALTER TABLE `submissions`
  ADD CONSTRAINT `fk_submissions_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
