import { Consumer } from '@/consumers/consumer.entity';
import { Exclude } from 'class-transformer';
import { ProviderEnum } from 'src/common/enums/providers.enum';
import { Entity, Column, PrimaryGeneratedColumn, OneToMany } from 'typeorm';

@Entity()
export class Provider {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({
    type: 'text',
    enum: ProviderEnum,
  })
  provider: ProviderEnum;

  @Column()
  displayName: string;

  @Column()
  @Exclude()
  accessToken: string;

  @Column()
  @Exclude()
  refreshToken: string;

  @Column({ default: false })
  enabled: boolean;

  @OneToMany(() => Consumer, (consumer) => consumer.provider)
  consumers: Consumer[];
}
